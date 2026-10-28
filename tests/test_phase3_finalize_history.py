from app.main import _select_phase3_finalize_history


def test_submitted_transcript_takes_precedence_over_persisted_history():
    submitted = [{"role": "user", "content": "I enjoy building prototypes."}]
    persisted = [{"role": "user", "content": "Old conversation."}]

    assert _select_phase3_finalize_history(submitted, persisted) == submitted


def test_persisted_history_is_used_when_no_transcript_is_submitted():
    persisted = [{"role": "user", "content": "Saved conversation."}]

    assert _select_phase3_finalize_history([], persisted) == persisted
    assert _select_phase3_finalize_history([], None) == []