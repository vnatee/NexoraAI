from approaches.promptmanager import PromptyManager


SYNTHETIC_RUNTIME_EXAMPLES = (
    "How did crypto do last year?",
    "Summarize Cryptocurrency Market Dynamics from last year",
    "What are my health plans?",
    "Show available health plans",
    "What is the deductible for the employee plan for a visit to Overlake in Bellevue?",
    "Overlake is in-network for the employee plan",
)


def test_query_rewrite_prompt_contains_only_real_conversation_messages():
    manager = PromptyManager()
    prompt = manager.load_prompt("chat_query_rewrite.prompty")

    messages = manager.render_prompt(
        prompt,
        {
            "user_query": "REAL USER QUESTION",
            "past_messages": [
                {"role": "user", "content": "REAL PRIOR QUESTION"},
                {"role": "assistant", "content": "REAL PRIOR ANSWER"},
            ],
        },
    )

    rendered = str(messages)
    assert "REAL USER QUESTION" in rendered
    assert "REAL PRIOR QUESTION" in rendered
    assert "REAL PRIOR ANSWER" in rendered
    for example in SYNTHETIC_RUNTIME_EXAMPLES:
        assert example not in rendered


def test_ask_prompt_does_not_send_synthetic_few_shot_messages():
    manager = PromptyManager()
    prompt = manager.load_prompt("ask_answer_question.prompty")

    messages = manager.render_prompt(
        prompt,
        {
            "override_prompt": "",
            "injected_prompt": "",
            "has_temporary_attachments": False,
            "user_query": "REAL USER QUESTION",
            "text_sources": ["knowledge.txt: verified fact"],
        },
    )

    rendered = str(messages)
    assert "REAL USER QUESTION" in rendered
    assert "verified fact" in rendered
    for example in SYNTHETIC_RUNTIME_EXAMPLES:
        assert example not in rendered
