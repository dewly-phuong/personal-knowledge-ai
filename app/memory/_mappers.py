"""
Pure mapping helpers: MongoDB documents → Chainlit TypedDict objects.
No async I/O; all functions are synchronous.
"""

from chainlit.types import FeedbackDict
from chainlit.step import StepDict
from chainlit.element import ElementDict


def doc_to_step(step: dict, feedback_map: dict | None = None) -> StepDict:
    """Map a cl_steps MongoDB document to a StepDict, optionally attaching feedback."""
    step_id = step["id"]
    feedback_dict = None
    if feedback_map:
        fb_doc = feedback_map.get(step_id)
        if fb_doc:
            feedback_dict = FeedbackDict(
                id=fb_doc["id"],
                forId=step_id,
                value=fb_doc["value"],
                comment=fb_doc.get("comment"),
            )

    return StepDict(
        id=step_id,
        name=step["name"],
        type=step["type"],
        threadId=step["threadId"],
        parentId=step.get("parentId"),
        streaming=step.get("streaming", False),
        waitForAnswer=step.get("waitForAnswer"),
        isError=step.get("isError"),
        metadata=step.get("metadata", {}),
        tags=step.get("tags"),
        input=step.get("input", ""),
        output=step.get("output", ""),
        createdAt=step.get("createdAt"),
        start=step.get("start"),
        end=step.get("end"),
        generation=step.get("generation"),
        showInput=step.get("showInput"),
        language=step.get("language"),
        feedback=feedback_dict,
    )


def _element_url(element: dict) -> str | None:
    """Resolve the URL for a stored element (plotly / file)."""
    el_url = element.get("url")
    if (
        element.get("type") == "plotly"
        and not el_url
        and element.get("_plotly_content")
    ):
        return f"/api/elements/{element['id']}/plotly"
    if (
        element.get("type") == "file"
        and not el_url
        and element.get("_file_content") is not None
    ):
        return f"/api/elements/{element['id']}/file"
    return el_url


def doc_to_element(element: dict, thread_id: str | None = None) -> ElementDict:
    """Map a cl_elements MongoDB document to an ElementDict."""
    return ElementDict(
        id=element["id"],
        threadId=thread_id or element.get("threadId"),
        type=element["type"],
        chainlitKey=element.get("chainlitKey"),
        url=_element_url(element),
        objectKey=element.get("objectKey"),
        name=element["name"],
        display=element["display"],
        size=element.get("size"),
        language=element.get("language"),
        autoPlay=element.get("autoPlay"),
        playerConfig=element.get("playerConfig"),
        page=element.get("page"),
        props=element.get("props", {}),
        forId=element.get("forId"),
        mime=element.get("mime"),
    )


def artifact_to_element(artifact: dict, thread_id: str) -> ElementDict:
    """Map an uploaded_artifacts document to an ElementDict."""
    return ElementDict(
        id=f"upload-{artifact['upload_id']}",
        threadId=thread_id,
        type="file",
        chainlitKey=None,
        url=f"/api/uploads/{artifact['upload_id']}/file",
        objectKey=None,
        name=f"{artifact['original_filename']}.processed.md",
        display="inline",
        size=None,
        language=None,
        autoPlay=None,
        playerConfig=None,
        page=None,
        props={},
        forId=None,
        mime="text/markdown",
    )
