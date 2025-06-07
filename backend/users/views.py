# users/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView # ADD THIS
from users.serializers import PasswordChangeSerializer, UserSerializer # UPDATE THIS
from django.contrib.auth import get_user_model

User = get_user_model()


class MeView(APIView):
    """
    An endpoint to get the current authenticated user's details.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class PasswordChangeView(generics.GenericAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = PasswordChangeSerializer
    permission_classes = (permissions.IsAuthenticated,) # Requires token authentication

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password updated successfully"}, status=status.HTTP_200_OK)