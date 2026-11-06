from rest_framework import serializers

from .models import User, UserProfile
from .roles import ROLES, permissions_for_roles


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=10, max_length=128)
    display_name = serializers.CharField(min_length=2, max_length=80)
    as_seller = serializers.BooleanField(default=False)
    accept_terms = serializers.BooleanField()

    def validate_accept_terms(self, v):
        if not v:
            raise serializers.ValidationError("Необходимо принять пользовательское соглашение")
        return v


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class TokenSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=128)
    new_password = serializers.CharField(write_only=True, min_length=10, max_length=128)


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=10, max_length=128)


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["display_name", "bio", "country", "language", "timezone"]


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "is_email_verified", "status", "date_joined", "profile", "roles", "permissions"]
        read_only_fields = ["id", "email", "is_email_verified", "status", "date_joined", "roles", "permissions"]

    def get_roles(self, obj):
        return sorted(obj.role_codes)

    def get_permissions(self, obj):
        return sorted(permissions_for_roles(obj.role_codes))

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", {})
        profile = instance.profile
        for k, v in profile_data.items():
            setattr(profile, k, v)
        profile.full_clean()
        profile.save()
        return instance


class RolesUpdateSerializer(serializers.Serializer):
    roles = serializers.ListField(child=serializers.ChoiceField(choices=list(ROLES)), allow_empty=False)
    comment = serializers.CharField(min_length=3, max_length=2000)


class PublicUserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source="profile.display_name")

    class Meta:
        model = User
        fields = ["id", "display_name"]
