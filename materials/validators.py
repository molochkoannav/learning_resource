import re
from urllib.parse import urlparse
from rest_framework import serializers


class YoutubeUrlValidator:
    def __init__(self, field):
        self.field = field

    def __call__(self, attrs):
        value = attrs.get(self.field)
        if not value:
            return

        urls = re.findall(r'https?://[^\s,]+', value)
        for url in urls:
            domain = urlparse(url).netloc.lower()
            allowed = (
                domain == 'youtube.com'
                or domain.endswith('.youtube.com')
                or domain == 'youtu.be'
                or domain.endswith('.youtu.be')
            )
            if not allowed:
                raise serializers.ValidationError(
                    f'Ссылка {url} запрещена. '
                    'Разрешены только ссылки на youtube.com'
                )
