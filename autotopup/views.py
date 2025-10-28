from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import AutoTopUp, AutoTopUpHistory
from .serializers import (
    AutoTopUpSerializer,
    AutoTopUpCreateSerializer,
    AutoTopUpDetailSerializer,
    AutoTopUpHistorySerializer
)
from rest_framework import serializers

class AutoTopUpCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create a new auto top-up",
        description="Schedule a new auto top-up. Funds will be locked from wallet.",
        request=AutoTopUpCreateSerializer,
        responses={
            201: AutoTopUpSerializer,
            400: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Airtime Auto Top-Up',
                value={
                    "service_type": "airtime",
                    "amount": "100.00",
                    "phone_number": "08012345678",
                    "network": "mtn",
                    "start_date": "2025-10-22T10:00:00Z",
                    "repeat_days": 7,
                    "is_active": True
                },
                request_only=True
            ),
            OpenApiExample(
                'Data Auto Top-Up',
                value={
                    "service_type": "data",
                    "amount": "500.00",
                    "phone_number": "08012345678",
                    "network": "mtn",
                    "plan": "mtn-1gb-30days",
                    "start_date": "2025-10-22T10:00:00Z",
                    "repeat_days": 30,
                    "is_active": True
                },
                request_only=True
            )
        ],
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def post(self, request):
        serializer = AutoTopUpCreateSerializer(data=request.data, context={'request': request})
        
        if serializer.is_valid(raise_exception=True):
            auto_topup = serializer.save()
            
            # Lock funds
            if not auto_topup.lock_funds():
                auto_topup.delete()
                return Response(
                    {'error': 'Failed to lock funds. Please try again.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            response_serializer = AutoTopUpSerializer(auto_topup)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GetUserAutoTopUpsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List user's auto top-ups",
        description="Retrieve all auto top-up schedules for the authenticated user.",
        responses={
            200: AutoTopUpSerializer(many=True),
        },
        tags=['Auto Top-Up']
    )
    def get(self, request):
        auto_topups = AutoTopUp.objects.filter(user=request.user).select_related('user__wallet')
        serializer = AutoTopUpSerializer(auto_topups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class AutoTopUpDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        try:
            return AutoTopUp.objects.select_related('user__wallet').get(pk=pk, user=user)
        except AutoTopUp.DoesNotExist:
            return None
    
    @extend_schema(
        summary="Get auto top-up details",
        description="Retrieve detailed information about a specific auto top-up including history",
        responses={
            200: AutoTopUpDetailSerializer,
            404: OpenApiTypes.OBJECT
        },
        tags=['Auto Top-Up']
    )
    def get(self, request, pk):
        auto_topup = self.get_object(pk, request.user)
        if not auto_topup:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AutoTopUpDetailSerializer(auto_topup)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        summary="Update auto top-up",
        description="Update an existing auto top-up schedule",
        request=AutoTopUpSerializer,
        responses={
            200: AutoTopUpSerializer,
            404: OpenApiTypes.OBJECT
        },
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def put(self, request, pk):
        auto_topup = self.get_object(pk, request.user)
        if not auto_topup:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AutoTopUpSerializer(auto_topup, data=request.data, partial=False)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Partially update auto top-up",
        description="Partially update an existing auto top-up schedule",
        request=AutoTopUpSerializer,
        responses={
            200: AutoTopUpSerializer,
            404: OpenApiTypes.OBJECT
        },
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def patch(self, request, pk):
        auto_topup = self.get_object(pk, request.user)
        if not auto_topup:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = AutoTopUpSerializer(auto_topup, data=request.data, partial=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Delete auto top-up",
        description="Delete an auto top-up schedule and unlock funds",
        responses={
            204: None,
            404: OpenApiTypes.OBJECT
        },
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def delete(self, request, pk):
        auto_topup = self.get_object(pk, request.user)
        if not auto_topup:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        auto_topup.unlock_funds()
        auto_topup.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AutoTopUpCancelView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Cancel auto top-up",
        description="Cancel an auto top-up schedule and unlock the reserved funds",
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        examples=[
            OpenApiExample(
                'Success Response',
                value={
                    "message": "Auto top-up cancelled successfully",
                    "unlocked_amount": "500.00"
                },
                response_only=True
            )
        ],
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def patch(self, request, pk):
        try:
            auto_topup = AutoTopUp.objects.get(pk=pk, user=request.user)
        except AutoTopUp.DoesNotExist:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not auto_topup.is_active:
            return Response(
                {'error': 'Auto top-up is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        unlocked_amount = auto_topup.locked_amount
        auto_topup.is_active = False
        auto_topup.save()
        
        if auto_topup.unlock_funds():
            return Response({
                'message': 'Auto top-up cancelled successfully',
                'unlocked_amount': str(unlocked_amount)
            }, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'Failed to unlock funds'},
            status=status.HTTP_400_BAD_REQUEST
        )


class AutoTopUpReactivateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Reactivate auto top-up",
        description="Reactivate a cancelled auto top-up. Funds will be locked again.",
        responses={
            200: OpenApiTypes.OBJECT,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT
        },
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def patch(self, request, pk):
        try:
            auto_topup = AutoTopUp.objects.get(pk=pk, user=request.user)
        except AutoTopUp.DoesNotExist:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if auto_topup.is_active:
            return Response(
                {'error': 'Auto top-up is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check wallet balance
        if auto_topup.user.wallet.balance < auto_topup.amount:
            return Response(
                {'error': 'Insufficient funds'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        auto_topup.is_active = True
        auto_topup.save()
        
        if auto_topup.lock_funds():
            return Response({
                'message': 'Auto top-up reactivated successfully',
                'locked_amount': str(auto_topup.locked_amount)
            }, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'Failed to lock funds'},
            status=status.HTTP_400_BAD_REQUEST
        )


class AutoTopUpHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get auto top-up history",
        description="Get execution history for a specific auto top-up",
        responses={
            200: AutoTopUpHistorySerializer(many=True),
            404: OpenApiTypes.OBJECT
        },
        tags=['Auto Top-Up']
    )
    def get(self, request, pk):
        try:
            auto_topup = AutoTopUp.objects.get(pk=pk, user=request.user)
        except AutoTopUp.DoesNotExist:
            return Response(
                {'error': 'Auto top-up not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        history = auto_topup.history.all()
        serializer = AutoTopUpHistorySerializer(history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
