import json
import os
from unittest.mock import MagicMock, patch

import pytest
from injector import Injector

from taskweaver.config.config_mgt import AppConfigSource
from taskweaver.logging import LoggingModule
from taskweaver.memory.experience import ExperienceGenerator

IN_GITHUB_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"


def test_experience_loading():
    """Test that handcrafted experiences can be loaded."""
    app_injector = Injector([LoggingModule])
    app_config = AppConfigSource(
        config_file_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "project/taskweaver_config.json",
        ),
        config={
            "llm.api_type": "openai",
            "llm.api_key": "test_key",
            "llm.model": "gpt-4",
        },
    )
    app_injector.binder.bind(AppConfigSource, to=app_config)
    experience_manager = app_injector.create_object(ExperienceGenerator)
    experience_manager.set_experience_dir(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data/experience",
        ),
    )

    experience_manager.refresh()
    experience_manager.load_experience()

    assert len(experience_manager.experience_list) == 1
    exp = experience_manager.experience_list[0]
    assert exp.exp_id == "test-exp-1"
    assert exp.who == ["CodeInterpreter"]
    assert len(exp.when) > 0
    assert len(exp.what) > 0
    assert "CSV" in exp.when or "file" in exp.when
    assert "Best Practices" in exp.what or "os.path.exists" in exp.what


@pytest.mark.skipif(IN_GITHUB_ACTIONS, reason="Test doesn't work in Github Actions.")
def test_experience_retrieval_with_llm():
    """Test LLM-based experience retrieval with mocked LLM response."""
    app_injector = Injector([LoggingModule])
    app_config = AppConfigSource(
        config_file_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "project/taskweaver_config.json",
        ),
        config={
            "llm.api_type": "openai",
            "llm.api_key": "test_key",
            "llm.model": "gpt-4",
        },
    )
    app_injector.binder.bind(AppConfigSource, to=app_config)
    experience_manager = app_injector.create_object(ExperienceGenerator)
    experience_manager.set_experience_dir(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data/experience",
        ),
    )

    user_query = "show top 10 data in ./data.csv"

    experience_manager.refresh()
    experience_manager.load_experience()

    # Mock LLM response to select the test experience (object format for json_object response_format)
    mock_llm_response = {"content": json.dumps({"test-exp-1": True})}
    experience_manager.llm_api.chat_completion = MagicMock(return_value=mock_llm_response)

    # CodeInterpreter should see it (matches who)
    experiences = experience_manager.retrieve_experience(user_query=user_query, role="CodeInterpreter")

    assert len(experiences) == 1
    assert experiences[0].exp_id == "test-exp-1"
    assert len(experiences[0].when) > 0
    assert len(experiences[0].what) > 0


def test_experience_who_filtering():
    """Test that experiences are filtered by role."""
    app_injector = Injector([LoggingModule])
    app_config = AppConfigSource(
        config_file_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "project/taskweaver_config.json",
        ),
        config={
            "llm.api_type": "openai",
            "llm.api_key": "test_key",
            "llm.model": "gpt-4",
        },
    )
    app_injector.binder.bind(AppConfigSource, to=app_config)
    experience_manager = app_injector.create_object(ExperienceGenerator)
    experience_manager.set_experience_dir(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data/experience",
        ),
    )

    experience_manager.refresh()
    experience_manager.load_experience()

    # Planner should see 0 candidates (test-exp-1 targets CodeInterpreter only)
    experiences = experience_manager.retrieve_experience(
        user_query="show data",
        role="Planner",
    )
    assert len(experiences) == 0


def test_experience_retrieval_no_selection():
    """Test LLM-based retrieval when LLM selects no experiences."""
    app_injector = Injector([LoggingModule])
    app_config = AppConfigSource(
        config_file_path=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "project/taskweaver_config.json",
        ),
        config={
            "llm.api_type": "openai",
            "llm.api_key": "test_key",
            "llm.model": "gpt-4",
        },
    )
    app_injector.binder.bind(AppConfigSource, to=app_config)
    experience_manager = app_injector.create_object(ExperienceGenerator)
    experience_manager.set_experience_dir(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data/experience",
        ),
    )

    user_query = "completely unrelated query about weather"

    experience_manager.refresh()
    experience_manager.load_experience()

    # Mock LLM response to select no experiences (object format)
    mock_llm_response = {"content": json.dumps({"test-exp-1": False})}
    experience_manager.llm_api.chat_completion = MagicMock(return_value=mock_llm_response)

    experiences = experience_manager.retrieve_experience(user_query=user_query)

    assert len(experiences) == 0
