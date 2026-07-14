from rest_framework import serializers

from apps.users.serializers import UserSerializer


class DetailResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()


class SocialLoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()
    is_new_user = serializers.BooleanField()
