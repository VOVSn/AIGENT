from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from users.serializers import PasswordChangeSerializer, UserSerializer, CalendarEventSerializer # UPDATE
from django.contrib.auth import get_user_model
from .models import CalendarEvent # UPDATE

User = get_user_model()


class MeView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# --- NEW VIEW ---
class CalendarEventListView(generics.ListAPIView):
    """
    API endpoint to list calendar events for the authenticated user.
    """
    serializer_class = CalendarEventSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return events belonging to the current user
        return CalendarEvent.objects.filter(user=self.request.user)


class PasswordChangeView(generics.GenericAPIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated successfully"}, status=status.HTTP_200_OK)