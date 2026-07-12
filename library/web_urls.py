from django.urls import path

from library import web_views

urlpatterns = [
    path("login/", web_views.login_view, name="login"),
    path("logout/", web_views.logout_view, name="logout"),
    path("", web_views.home_view, name="home"),
    path("models/", web_views.models_list_view, name="models_list"),
    path("models/save/", web_views.model_save_view, name="model_save"),
    path("settings/", web_views.settings_view, name="settings"),
    path("models/<int:pk>/", web_views.model_detail_view, name="model_detail"),
    path("collections/", web_views.collections_list_view, name="collections_list"),
    path("collections/<slug:slug>/", web_views.collection_detail_view, name="collection_detail"),
]
