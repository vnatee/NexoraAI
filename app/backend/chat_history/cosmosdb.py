import asyncio
import os
import time
from typing import Any, Union

from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import AzureDeveloperCliCredential, ManagedIdentityCredential
from quart import Blueprint, current_app, jsonify, make_response, request

from config import (
    CONFIG_CHAT_ATTACHMENT_STORE,
    CONFIG_CHAT_HISTORY_COSMOS_ENABLED,
    CONFIG_CHAT_HISTORY_DATABASE_ENABLED,
    CONFIG_COSMOS_HISTORY_CLIENT,
    CONFIG_COSMOS_HISTORY_CONTAINER,
    CONFIG_COSMOS_HISTORY_VERSION,
    CONFIG_CREDENTIAL,
)
from core.attachment_store import AttachmentNotFoundError, AttachmentStore
from decorators import authenticated
from error import error_response
from mongo_table_connecters.chat_attachment_index import (
    delete_conversation_attachment_chunks,
)
from mongo_table_connecters.chat_attachment_metadata import (
    delete_conversation_attachment_metadata,
    list_conversation_attachment_metadata,
)
from mongo_table_connecters.chat_history import (
    delete_session,
    ensure_indexes,
    get_session,
    insert_deletion_audit,
    list_expired_sessions,
    list_sessions,
    upsert_session,
)

chat_history_cosmosdb_bp = Blueprint("chat_history_cosmos", __name__, static_folder="static")
_mongo_cleanup_task: asyncio.Task | None = None


def _owner_id(auth_claims: dict[str, Any]) -> str:
    return str(
        auth_claims.get("oid")
        or auth_claims.get("sub")
        or auth_claims.get("preferred_username")
        or ""
    )


async def _delete_conversation_dependencies(owner_id: str, conversation_id: str) -> int:
    items = await asyncio.to_thread(
        list_conversation_attachment_metadata,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    store: AttachmentStore | None = current_app.config.get(CONFIG_CHAT_ATTACHMENT_STORE)
    if items and store is None:
        raise RuntimeError("Chat attachment storage is unavailable for conversation cleanup")
    for item in items:
        assert store is not None
        try:
            await store.delete(
                str(item["_id"]),
                owner_id=owner_id,
                conversation_id=conversation_id,
            )
        except AttachmentNotFoundError:
            pass
    await asyncio.to_thread(
        delete_conversation_attachment_chunks,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    await asyncio.to_thread(
        delete_conversation_attachment_metadata,
        owner_id=owner_id,
        conversation_id=conversation_id,
    )
    return len(items)


async def _delete_database_history_session(
    session: dict[str, Any], *, actor_id: str, reason: str
) -> bool:
    session_id = str(session.get("_id") or "")
    owner_id = str(session.get("owner_id") or "")
    conversation_id = str(session.get("conversation_id") or session_id)
    attachment_count = await _delete_conversation_dependencies(owner_id, conversation_id)
    deleted = await asyncio.to_thread(delete_session, session_id, owner_id)
    if deleted:
        await asyncio.to_thread(
            insert_deletion_audit,
            actor_id=actor_id,
            reason=reason,
            conversation_count=1,
            attachment_count=attachment_count,
        )
    return deleted


async def _mongo_cleanup_loop(interval_seconds: float) -> None:
    while True:
        try:
            expired = await asyncio.to_thread(list_expired_sessions)
            deleted = 0
            for session in expired:
                try:
                    if await _delete_database_history_session(
                        session, actor_id="system", reason="retention"
                    ):
                        deleted += 1
                except Exception:
                    current_app.logger.exception(
                        "Unable to cascade expired Chat history session cleanup"
                    )
            if deleted:
                current_app.logger.info("Expired Chat history sessions removed: %d", deleted)
        except asyncio.CancelledError:
            raise
        except Exception:
            current_app.logger.exception("Unable to clean expired Chat history")
        await asyncio.sleep(interval_seconds)


@chat_history_cosmosdb_bp.post("/chat_history")
@authenticated
async def post_chat_history(auth_claims: dict[str, Any]):
    if current_app.config.get(CONFIG_CHAT_HISTORY_DATABASE_ENABLED):
        try:
            payload = await request.get_json()
            owner_id = _owner_id(auth_claims)
            if not owner_id:
                return jsonify({"error": "User identity not found"}), 401
            await asyncio.to_thread(
                upsert_session,
                str(payload.get("id") or ""),
                owner_id,
                payload.get("answers"),
                str(payload.get("team_id") or "") or None,
                str(payload.get("conversation_id") or "") or None,
            )
            return jsonify({}), 201
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            return error_response(error, "/chat_history")
    if not current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]:
        return jsonify({"error": "Chat history not enabled"}), 400

    container: ContainerProxy = current_app.config[CONFIG_COSMOS_HISTORY_CONTAINER]
    if not container:
        return jsonify({"error": "Chat history not enabled"}), 400

    entra_oid = auth_claims.get("oid")
    if not entra_oid:
        return jsonify({"error": "User OID not found"}), 401

    try:
        request_json = await request.get_json()
        session_id = request_json.get("id")
        message_pairs = request_json.get("answers")
        first_question = message_pairs[0][0]
        title = first_question + "..." if len(first_question) > 50 else first_question
        timestamp = int(time.time() * 1000)

        # Insert the session item:
        session_item = {
            "id": session_id,
            "version": current_app.config[CONFIG_COSMOS_HISTORY_VERSION],
            "session_id": session_id,
            "entra_oid": entra_oid,
            "type": "session",
            "title": title,
            "timestamp": timestamp,
        }

        message_pair_items = []
        # Now insert a message item for each question/response pair:
        for ind, message_pair in enumerate(message_pairs):
            message_pair_items.append(
                {
                    "id": f"{session_id}-{ind}",
                    "version": current_app.config[CONFIG_COSMOS_HISTORY_VERSION],
                    "session_id": session_id,
                    "entra_oid": entra_oid,
                    "type": "message_pair",
                    "question": message_pair[0],
                    "response": message_pair[1],
                }
            )

        batch_operations = [("upsert", (session_item,))] + [
            ("upsert", (message_pair_item,)) for message_pair_item in message_pair_items
        ]
        await container.execute_item_batch(batch_operations=batch_operations, partition_key=[entra_oid, session_id])
        return jsonify({}), 201
    except Exception as error:
        return error_response(error, "/chat_history")


@chat_history_cosmosdb_bp.get("/chat_history/sessions")
@authenticated
async def get_chat_history_sessions(auth_claims: dict[str, Any]):
    if current_app.config.get(CONFIG_CHAT_HISTORY_DATABASE_ENABLED):
        try:
            owner_id = _owner_id(auth_claims)
            if not owner_id:
                return jsonify({"error": "User identity not found"}), 401
            count = max(1, min(int(request.args.get("count", 10)), 100))
            sessions, token = await asyncio.to_thread(
                list_sessions, owner_id, count, request.args.get("continuation_token")
            )
            return jsonify({"sessions": sessions, "continuation_token": token}), 200
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        except Exception as error:
            return error_response(error, "/chat_history/sessions")
    if not current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]:
        return jsonify({"error": "Chat history not enabled"}), 400

    container: ContainerProxy = current_app.config[CONFIG_COSMOS_HISTORY_CONTAINER]
    if not container:
        return jsonify({"error": "Chat history not enabled"}), 400

    entra_oid = auth_claims.get("oid")
    if not entra_oid:
        return jsonify({"error": "User OID not found"}), 401

    try:
        count = int(request.args.get("count", 10))
        continuation_token = request.args.get("continuation_token")

        res = container.query_items(
            query="SELECT c.id, c.entra_oid, c.title, c.timestamp FROM c WHERE c.entra_oid = @entra_oid AND c.type = @type ORDER BY c.timestamp DESC",
            parameters=[dict(name="@entra_oid", value=entra_oid), dict(name="@type", value="session")],
            partition_key=[entra_oid],
            max_item_count=count,
        )

        pager = res.by_page(continuation_token)

        # Get the first page, and the continuation token
        sessions = []
        try:
            page = await pager.__anext__()
            continuation_token = pager.continuation_token  # type: ignore

            async for item in page:
                sessions.append(
                    {
                        "id": item.get("id"),
                        "entra_oid": item.get("entra_oid"),
                        "title": item.get("title", "untitled"),
                        "timestamp": item.get("timestamp"),
                    }
                )

        # If there are no more pages, StopAsyncIteration is raised
        except StopAsyncIteration:
            continuation_token = None

        return jsonify({"sessions": sessions, "continuation_token": continuation_token}), 200

    except Exception as error:
        return error_response(error, "/chat_history/sessions")


@chat_history_cosmosdb_bp.get("/chat_history/sessions/<session_id>")
@authenticated
async def get_chat_history_session(auth_claims: dict[str, Any], session_id: str):
    if current_app.config.get(CONFIG_CHAT_HISTORY_DATABASE_ENABLED):
        try:
            owner_id = _owner_id(auth_claims)
            if not owner_id:
                return jsonify({"error": "User identity not found"}), 401
            item = await asyncio.to_thread(get_session, session_id, owner_id)
            if not item:
                return jsonify({"error": "Chat history session not found"}), 404
            return jsonify({"id": session_id, "answers": item.get("answers") or []}), 200
        except Exception as error:
            return error_response(error, f"/chat_history/sessions/{session_id}")
    if not current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]:
        return jsonify({"error": "Chat history not enabled"}), 400

    container: ContainerProxy = current_app.config[CONFIG_COSMOS_HISTORY_CONTAINER]
    if not container:
        return jsonify({"error": "Chat history not enabled"}), 400

    entra_oid = auth_claims.get("oid")
    if not entra_oid:
        return jsonify({"error": "User OID not found"}), 401

    try:
        res = container.query_items(
            query=(
                "SELECT * FROM c WHERE c.entra_oid = @entra_oid "
                "AND c.session_id = @session_id AND c.type = @type"
            ),
            parameters=[
                dict(name="@entra_oid", value=entra_oid),
                dict(name="@session_id", value=session_id),
                dict(name="@type", value="message_pair"),
            ],
            partition_key=[entra_oid, session_id],
        )

        message_pairs = []
        async for page in res.by_page():
            async for item in page:
                message_pairs.append([item["question"], item["response"]])

        return (
            jsonify(
                {
                    "id": session_id,
                    "entra_oid": entra_oid,
                    "answers": message_pairs,
                }
            ),
            200,
        )
    except Exception as error:
        return error_response(error, f"/chat_history/sessions/{session_id}")


@chat_history_cosmosdb_bp.delete("/chat_history/sessions/<session_id>")
@authenticated
async def delete_chat_history_session(auth_claims: dict[str, Any], session_id: str):
    if current_app.config.get(CONFIG_CHAT_HISTORY_DATABASE_ENABLED):
        try:
            owner_id = _owner_id(auth_claims)
            if not owner_id:
                return jsonify({"error": "User identity not found"}), 401
            item = await asyncio.to_thread(get_session, session_id, owner_id)
            if item:
                await _delete_database_history_session(
                    item, actor_id=owner_id, reason="user"
                )
            return await make_response("", 204)
        except Exception as error:
            return error_response(error, f"/chat_history/sessions/{session_id}")
    if not current_app.config[CONFIG_CHAT_HISTORY_COSMOS_ENABLED]:
        return jsonify({"error": "Chat history not enabled"}), 400

    container: ContainerProxy = current_app.config[CONFIG_COSMOS_HISTORY_CONTAINER]
    if not container:
        return jsonify({"error": "Chat history not enabled"}), 400

    entra_oid = auth_claims.get("oid")
    if not entra_oid:
        return jsonify({"error": "User OID not found"}), 401

    try:
        res = container.query_items(
            query="SELECT c.id FROM c WHERE c.entra_oid = @entra_oid AND c.session_id = @session_id",
            parameters=[
                dict(name="@entra_oid", value=entra_oid),
                dict(name="@session_id", value=session_id),
            ],
            partition_key=[entra_oid, session_id],
        )

        ids_to_delete = []
        async for page in res.by_page():
            async for item in page:
                ids_to_delete.append(item["id"])

        batch_operations = [("delete", (id,)) for id in ids_to_delete]
        await container.execute_item_batch(batch_operations=batch_operations, partition_key=[entra_oid, session_id])
        return await make_response("", 204)
    except Exception as error:
        return error_response(error, f"/chat_history/sessions/{session_id}")


@chat_history_cosmosdb_bp.before_app_serving
async def setup_clients():
    global _mongo_cleanup_task
    if os.getenv("USE_CHAT_HISTORY_DATABASE", "").lower() == "true":
        await asyncio.to_thread(ensure_indexes)
        interval = max(60.0, float(os.getenv("CHAT_HISTORY_CLEANUP_INTERVAL_SECONDS", "3600")))
        _mongo_cleanup_task = asyncio.create_task(_mongo_cleanup_loop(interval))
    USE_CHAT_HISTORY_COSMOS = os.getenv("USE_CHAT_HISTORY_COSMOS", "").lower() == "true"
    AZURE_COSMOSDB_ACCOUNT = os.getenv("AZURE_COSMOSDB_ACCOUNT")
    AZURE_CHAT_HISTORY_DATABASE = os.getenv("AZURE_CHAT_HISTORY_DATABASE")
    AZURE_CHAT_HISTORY_CONTAINER = os.getenv("AZURE_CHAT_HISTORY_CONTAINER")

    azure_credential: Union[AzureDeveloperCliCredential, ManagedIdentityCredential] = current_app.config[
        CONFIG_CREDENTIAL
    ]

    if USE_CHAT_HISTORY_COSMOS:
        current_app.logger.info("USE_CHAT_HISTORY_COSMOS is true, setting up CosmosDB client")
        if not AZURE_COSMOSDB_ACCOUNT:
            raise ValueError("AZURE_COSMOSDB_ACCOUNT must be set when USE_CHAT_HISTORY_COSMOS is true")
        if not AZURE_CHAT_HISTORY_DATABASE:
            raise ValueError("AZURE_CHAT_HISTORY_DATABASE must be set when USE_CHAT_HISTORY_COSMOS is true")
        if not AZURE_CHAT_HISTORY_CONTAINER:
            raise ValueError("AZURE_CHAT_HISTORY_CONTAINER must be set when USE_CHAT_HISTORY_COSMOS is true")
        cosmos_client = CosmosClient(
            url=f"https://{AZURE_COSMOSDB_ACCOUNT}.documents.azure.com:443/", credential=azure_credential
        )
        cosmos_db = cosmos_client.get_database_client(AZURE_CHAT_HISTORY_DATABASE)
        cosmos_container = cosmos_db.get_container_client(AZURE_CHAT_HISTORY_CONTAINER)

        current_app.config[CONFIG_COSMOS_HISTORY_CLIENT] = cosmos_client
        current_app.config[CONFIG_COSMOS_HISTORY_CONTAINER] = cosmos_container
        current_app.config[CONFIG_COSMOS_HISTORY_VERSION] = os.environ["AZURE_CHAT_HISTORY_VERSION"]


@chat_history_cosmosdb_bp.after_app_serving
async def close_clients():
    global _mongo_cleanup_task
    if _mongo_cleanup_task:
        _mongo_cleanup_task.cancel()
        try:
            await _mongo_cleanup_task
        except asyncio.CancelledError:
            pass
        _mongo_cleanup_task = None
    if current_app.config.get(CONFIG_COSMOS_HISTORY_CLIENT):
        cosmos_client: CosmosClient = current_app.config[CONFIG_COSMOS_HISTORY_CLIENT]
        await cosmos_client.close()
