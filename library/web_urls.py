from django.urls import path

from library import web_views

urlpatterns = [
    path("login/", web_views.login_view, name="login"),
    path("logout/", web_views.logout_view, name="logout"),
    path("sw.js", web_views.service_worker_view, name="service_worker"),
    path("manifest.webmanifest", web_views.manifest_view, name="web_manifest"),
    path("share/", web_views.share_target_view, name="share_target"),
    path("", web_views.home_view, name="home"),
    path("models/", web_views.models_list_view, name="models_list"),
    path("models/save/", web_views.model_save_view, name="model_save"),
    path("settings/", web_views.settings_view, name="settings"),
    path("settings/about-checks/", web_views.about_checks_view, name="about_checks"),
    path("settings/scan-worker-check/", web_views.scan_worker_check_view, name="scan_worker_check"),
    path("settings/scan-worker-save/", web_views.scan_worker_save_view, name="scan_worker_save"),
    path("models/<int:pk>/", web_views.model_detail_view, name="model_detail"),
    path("models/<int:pk>/preview/<int:file_id>/", web_views.model_preview_view, name="model_preview"),
    path("collections/", web_views.collections_list_view, name="collections_list"),
    path("collections/<slug:slug>/", web_views.collection_detail_view, name="collection_detail"),
    path("scan/", web_views.scan_list_view, name="scan_list"),
    path("scan/chunk/", web_views.scan_chunk_upload_view, name="scan_chunk_upload"),
    path("scan/chunk/complete/", web_views.scan_chunk_complete_view, name="scan_chunk_complete"),
    path("scan/<uuid:job_id>/", web_views.scan_job_view, name="scan_job"),
    path("scan/<uuid:job_id>/status/", web_views.scan_status_view, name="scan_status"),
    path("scan/<uuid:job_id>/import/", web_views.scan_import_view, name="scan_import"),
    path("scan/<uuid:job_id>/download/<str:filename>/", web_views.scan_download_view, name="scan_download"),
]
