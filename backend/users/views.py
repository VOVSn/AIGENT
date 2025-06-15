# users/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView # ADD THIS
from users.serializers import PasswordChangeSerializer, UserSerializer # UPDATE THIS
from django.contrib.auth import get_user_model

User = get_user_model()


class MeView(APIView):
    """
    An endpoint to get or update the current authenticated user's details.
    """
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        """
        Allows partial updates to the user model (e.g., updating the timezone).
        """
        user = request.user
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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