from __future__ import annotations

import importlib


def test_core_modules_import_without_heavy_bertopic_worker() -> None:
    modules = [
        "app.main",
        "app.ui",
        "app.session_state",
        "app.modules.dashboard",
        "app.modules.data_input",
        "app.modules.llm_screening",
        "app.modules.bertopic_analysis",
        "app.modules.pdf_extraction",
        "app.modules.profile",
        "app.modules.project_list",
        "app.services.auth",
        "app.services.db",
        "app.services.llm",
        "app.services.projects",
        "app.services.storage",
        "app.services.screening",
        "app.services.bertopic_service",
        "app.services.pdf_service",
    ]
    for module_name in modules:
        importlib.import_module(module_name)
