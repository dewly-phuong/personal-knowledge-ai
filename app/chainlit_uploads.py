import logging
import os

import chainlit as cl

from app.services.upload_artifacts import process_upload

logger = logging.getLogger(__name__)


async def process_message_uploads(
    message: cl.Message, session_id: str, user
) -> list[str]:
    upload_ids = []
    for element in message.elements or []:
        file_path = getattr(element, "path", None)
        if not file_path:
            continue
        try:
            artifact = process_upload(
                file_path=file_path,
                original_filename=getattr(element, "name", None),
                session_id=session_id,
                user_id=user.identifier if user else None,
                mime_type=getattr(element, "mime", None),
            )
            if artifact.get("status") == "processed":
                await _send_processed_message(artifact)
                upload_ids.append(artifact["upload_id"])
            else:
                await cl.Message(
                    content=(
                        f"Không xử lý được file "
                        f"`{artifact.get('original_filename', 'unknown')}`: "
                        f"{artifact.get('error', 'unknown error')}"
                    )
                ).send()
        except Exception as e:
            logger.warning(f"Failed to process uploaded file: {e}")
            await cl.Message(content=f"Không xử lý được file upload: {e}").send()
    return upload_ids


async def _send_processed_message(artifact: dict) -> None:
    elements = _processed_elements(artifact)
    if artifact.get("duplicate"):
        await cl.Message(
            content=(
                f"File `{artifact['original_filename']}` đã tồn tại trong "
                f"session này, hệ thống tái sử dụng bản đã xử lý. "
                f"Upload ID: `{artifact['upload_id']}`"
            ),
            elements=elements,
        ).send()
        return

    await cl.Message(
        content=(
            f"Đã xử lý file `{artifact['original_filename']}` "
            f"và thêm vào context phiên chat. Upload ID: `{artifact['upload_id']}`"
        ),
        elements=elements,
    ).send()


def _processed_elements(artifact: dict) -> list[cl.File]:
    processed_path = artifact.get("processed_path")
    if not processed_path or not os.path.exists(processed_path):
        return []
    return [
        cl.File(
            name=f"{artifact['original_filename']}.processed.md",
            path=processed_path,
            display="inline",
            mime="text/markdown",
        )
    ]
