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
from notifications.utils import send_notification

class AutoTopUpCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Create a new auto top-up",
        description="Schedule a new auto top-up. Funds will be locked from wallet. Requires transaction PIN.",
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
                    "start_date": "2025-11-02T10:00:00Z",
                    "repeat_days": 7,
                    "is_active": True,
                    "transaction_pin": "1234"
                },
                request_only=True
            ),
        ],
        tags=['Auto Top-Up']
    )
    @transaction.atomic
    def post(self, request):
        # Get and validate PIN first
        transaction_pin = request.data.get('transaction_pin')
        
        if not transaction_pin:
            return Response(
                {'error': 'Transaction PIN is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has set PIN
        if not request.user.pin_is_set:
            return Response(
                {'error': 'Please set your transaction PIN first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify PIN
        if not request.user.verify_transaction_pin(transaction_pin):
            return Response(
                {'error': 'Invalid transaction PIN'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove PIN from data before serialization
        data = request.data.copy()
        data.pop('transaction_pin', None)
        
        serializer = AutoTopUpCreateSerializer(data=data, context={'request': request})
        
        if serializer.is_valid(raise_exception=True):
            auto_topup = serializer.save()
            
            # Lock funds
            if not auto_topup.lock_funds():
                auto_topup.delete()
                return Response(
                    {'error': 'Failed to lock funds. Please try again.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Send success notification asynchronously (non-blocking)
            try:
                service_label = "Airtime" if auto_topup.service_type == "airtime" else "Data"
                frequency = "one-time" if auto_topup.repeat_days == 0 else f"every {auto_topup.repeat_days} days"
                
                # This now returns immediately as email is queued
                send_notification(
                    user=request.user,
                    title="Auto Top-Up Created",
                    message=f"{service_label} auto top-up of ₦{auto_topup.amount} scheduled {frequency}. ₦{auto_topup.locked_amount} has been locked from your wallet.",
                    notification_type='success',
                    email_subject="BlueSea Mobile - Auto Top-Up Scheduled",
                    context={
                        'service_type': service_label,
                        'amount': auto_topup.amount,
                        'phone_number': auto_topup.phone_number,
                        'network': auto_topup.network.upper() if auto_topup.network else 'N/A',
                        'start_date': auto_topup.start_date,
                        'frequency': frequency,
                        'locked_amount': auto_topup.locked_amount,
                    }
                )
            except Exception as e:
                # Don't fail the request if notification fails
                pass
            
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
        auto_topups = AutoTopUp.objects.filter(
            user=request.user
        ).select_related('user__wallet').order_by('-created_at')
        
        serializer = AutoTopUpSerializer(auto_topups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class AutoTopUpDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        try:
            return AutoTopUp.objects.select_related(
                'user__wallet'
            ).prefetch_related('history').get(pk=pk, user=user)
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
            updated_topup = serializer.save()
            
            # Send notification asynchronously
            try:
                send_notification(
                    user=request.user,
                    title="Auto Top-Up Updated",
                    message=f"Your {updated_topup.service_type} auto top-up schedule has been updated.",
                    notification_type='info'
                )
            except Exception:
                pass
            
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
            updated_topup = serializer.save()
            
            # Send notification asynchronously
            try:
                send_notification(
                    user=request.user,
                    title="Auto Top-Up Updated",
                    message=f"Your {updated_topup.service_type} auto top-up schedule has been updated.",
                    notification_type='info'
                )
            except Exception:
                pass
            
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
        
        unlocked_amount = auto_topup.locked_amount
        service_type = auto_topup.service_type
        
        auto_topup.unlock_funds()
        auto_topup.delete()
        
        # Send notification asynchronously
        try:
            send_notification(
                user=request.user,
                title="Auto Top-Up Deleted",
                message=f"Your {service_type} auto top-up has been deleted. ₦{unlocked_amount} has been returned to your wallet.",
                notification_type='info',
                context={
                    'unlocked_amount': unlocked_amount,
                    'service_type': service_type
                }
            )
        except Exception:
            pass
        
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
            auto_topup = AutoTopUp.objects.select_related('user__wallet').get(pk=pk, user=request.user)
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
        service_type = auto_topup.service_type
        auto_topup.is_active = False
        auto_topup.save()
        
        if auto_topup.unlock_funds():
            # Send notification asynchronously
            try:
                send_notification(
                    user=request.user,
                    title="Auto Top-Up Cancelled",
                    message=f"Your {service_type} auto top-up has been cancelled. ₦{unlocked_amount} has been returned to your wallet.",
                    notification_type='warning',
                    email_subject="BlueSea Mobile - Auto Top-Up Cancelled",
                    context={
                        'service_type': service_type,
                        'unlocked_amount': unlocked_amount,
                    }
                )
            except Exception:
                pass
            
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
        # Get and validate PIN first
        transaction_pin = request.data.get('transaction_pin')
        
        if not transaction_pin:
            return Response(
                {'error': 'Transaction PIN is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user has set PIN
        if not request.user.pin_is_set:
            return Response(
                {'error': 'Please set your transaction PIN first'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify PIN
        if not request.user.verify_transaction_pin(transaction_pin):
            return Response(
                {'error': 'Invalid transaction PIN'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Remove PIN from data before serialization
        data = request.data.copy()
        data.pop('transaction_pin', None)
        
        try:
            auto_topup = AutoTopUp.objects.select_related('user__wallet').get(pk=pk, user=request.user)
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
            # Send notification asynchronously
            try:
                send_notification(
                    user=request.user,
                    title="Auto Top-Up Reactivated",
                    message=f"Your {auto_topup.service_type} auto top-up has been reactivated. ₦{auto_topup.locked_amount} has been locked from your wallet.",
                    notification_type='success',
                    email_subject="BlueSea Mobile - Auto Top-Up Reactivated",
                    context={
                        'service_type': auto_topup.service_type,
                        'locked_amount': auto_topup.locked_amount,
                        'next_run': auto_topup.next_run,
                    }
                )
            except Exception:
                pass
            
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
        
        # Optimized query
        history = auto_topup.history.all().order_by('-executed_at')
        serializer = AutoTopUpHistorySerializer(history, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
