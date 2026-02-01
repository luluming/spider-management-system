"""spider_management URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login', RedirectView.as_view(url='/accounts/login/', permanent=True)),
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=True)),
    path('accounts/', include('accounts.urls')),
    path('', include('spiders.urls')),
]

# 开发环境下提供媒体文件服务及静态文件服务（便于调试）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # 在开发环境直接从 STATICFILES_DIRS 提供静态文件，确保 CSS/JS 以正确的 Content-Type 返回
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])

# 当 DEBUG=False 且没有前端静态文件服务器时，提供静态文件服务（仅用于临时恢复）
if not settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

