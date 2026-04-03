from rest_framework import permissions, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import UserSettings
from .serializers import UserSettingsSerializer

class MeUserSettingsViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def _get(self, request):
        us, _ = UserSettings.objects.get_or_create(user=request.user)
        return us

    def list(self, request):
        us = self._get(request)
        return Response(UserSettingsSerializer(us).data)


    def partial_update(self, request, pk=None):
        us = self._get(request)
        ser = UserSettingsSerializer(us, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    @action(detail=False, methods=['post'], url_path=r'filters/(?P<key>[^/]+)')
    def save_filters(self, request, key=None):
        us = self._get(request)
        data = dict(request.data)
        us.saved_filters[key] = data
        us.save(update_fields=['saved_filters'])
        return Response({'status':'ok','key':key})

    @action(detail=False, methods=['get'], url_path=r'filters/(?P<key>[^/]+)')
    def get_filters(self, request, key=None):
        us = self._get(request)
        return Response(us.saved_filters.get(key, {}))
