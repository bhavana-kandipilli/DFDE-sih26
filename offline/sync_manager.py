#!/usr/bin/env python3
"""
Offline Sync Manager for Digital Field Drug Evidence System.

Manages the transition from offline storage to server synchronization:
- Exponential backoff with jitter on retry
- Transactional resume of partial syncs
- Idempotency key tracking for duplicate prevention
- Conflict resolution
- Strict verification gate handling (SYNC_REJECTED -> VERIFICATION_FAILED)
"""

import time
import random
import logging
from typing import Dict, Any, List, Optional, Callable
from offline.local_storage import EncryptedLocalStorage

logger = logging.getLogger("offline_sync_manager")

class SyncStatus:
    PENDING_SYNC = "PENDING_SYNC"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    SYNC_FAILED = "SYNC_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"

class SyncManager:
    """
    Manages background/foreground cloud synchronization with resilience.
    """

    def __init__(
        self,
        local_store: EncryptedLocalStorage,
        device_id: str = "FIELD-TERMINAL-01",
        max_retries: int = 5,
        base_backoff_sec: float = 0.2
    ):
        self.local_store = local_store
        self.device_id = device_id
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec

    def get_pending_count(self) -> int:
        items = self.local_store.get_sync_items(status=SyncStatus.PENDING_SYNC)
        return len(items)

    def synchronize_all(
        self,
        api_post_func: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synchronizes all pending and failed (retryable) items to the server.

        Args:
            api_post_func: A callable `func(endpoint, payload) -> response_dict`
                           (can be requests.post, httpx.post, or TestClient.post).

        Returns:
            Summary of sync execution.
        """
        pending_items = self.local_store.get_sync_items(status=SyncStatus.PENDING_SYNC)
        # Also retry items that transiently failed and haven't exceeded max_retries
        failed_items = [
            item for item in self.local_store.get_sync_items(status=SyncStatus.SYNC_FAILED)
            if item["retry_count"] < self.max_retries
        ]

        items_to_sync = pending_items + failed_items
        results = {
            "total": len(items_to_sync),
            "synced": 0,
            "failed": 0,
            "verification_failed": 0,
            "details": []
        }

        for item in items_to_sync:
            idempotency_key = item["idempotency_key"]
            resource_type = item["resource_type"]
            resource_id = item["resource_id"]

            # Mark status SYNCING
            self.local_store.update_sync_status(idempotency_key, SyncStatus.SYNCING)

            sync_res = self._sync_single_item(item, api_post_func)
            results["details"].append(sync_res)

            if sync_res["status"] == SyncStatus.SYNCED:
                results["synced"] += 1
                self.local_store.update_sync_status(idempotency_key, SyncStatus.SYNCED)
            elif sync_res["status"] == SyncStatus.VERIFICATION_FAILED:
                results["verification_failed"] += 1
                self.local_store.update_sync_status(
                    idempotency_key,
                    SyncStatus.VERIFICATION_FAILED,
                    error_message=sync_res.get("error")
                )
            else:
                results["failed"] += 1
                self.local_store.update_sync_status(
                    idempotency_key,
                    SyncStatus.SYNC_FAILED,
                    error_message=sync_res.get("error")
                )

        return results

    def sync_all_pending(
        self,
        api_post_func: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Alias for synchronize_all returning list of item results directly.
        """
        summary = self.synchronize_all(api_post_func)
        return summary["details"]

    def _sync_single_item(
        self,
        item: Dict[str, Any],
        api_post_func: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Executes sync for a single item with exponential backoff and verification handling.
        """
        idempotency_key = item["idempotency_key"]
        resource_id = item["resource_id"]
        attempt = 0

        # Build full bundle
        bundle = self.local_store.get_full_bundle_by_evidence_id(resource_id)
        if not bundle:
            return {
                "idempotency_key": idempotency_key,
                "status": SyncStatus.SYNC_FAILED,
                "error": f"Evidence bundle '{resource_id}' missing from local vault."
            }

        sync_payload = {
            "device_id": self.device_id,
            "client_sync_timestamp": bundle["evidence"]["created_at"],
            "items": [
                {
                    "client_record_id": idempotency_key,
                    "type": "evidence_bundle",
                    "data": bundle
                }
            ]
        }

        while attempt < self.max_retries:
            attempt += 1
            try:
                response = api_post_func("/sync", sync_payload)

                # Check if server rejected due to verification / tamper detection
                server_status = response.get("status")
                if server_status in ("SYNC_REJECTED", "VERIFICATION_FAILED"):
                    return {
                        "idempotency_key": idempotency_key,
                        "status": SyncStatus.VERIFICATION_FAILED,
                        "error": response.get("detail") or response.get("error") or "Server hash verification rejected."
                    }

                if server_status in ("SUCCESS", "COMPLETED", "SYNCED"):
                    return {
                        "idempotency_key": idempotency_key,
                        "status": SyncStatus.SYNCED,
                        "server_response": response
                    }

                # If status code error or unexpected response
                error_msg = response.get("detail") or str(response)
                raise RuntimeError(f"Server rejected sync: {error_msg}")

            except Exception as exc:
                if attempt >= self.max_retries:
                    return {
                        "idempotency_key": idempotency_key,
                        "status": SyncStatus.SYNC_FAILED,
                        "error": f"Max retries exceeded: {str(exc)}"
                    }

                # Exponential backoff with jitter
                sleep_sec = (self.base_backoff_sec * (2 ** (attempt - 1))) + (random.uniform(0.01, 0.05))
                time.sleep(sleep_sec)

        return {
            "idempotency_key": idempotency_key,
            "status": SyncStatus.SYNC_FAILED,
            "error": "Sync attempt terminated."
        }
