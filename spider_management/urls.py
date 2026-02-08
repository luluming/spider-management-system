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

# 提供媒体文件及静态文件服务（DEBUG 时提供 media，静态文件统一从 STATIC_ROOT 提供）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# 静态文件从 STATIC_ROOT 提供（需先运行 collectstatic），确保 _tokens.css 等 theme 静态文件正确加载
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

