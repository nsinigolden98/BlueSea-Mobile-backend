from django.shortcuts import render, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import TicketVendor

@staff_member_required
def reject_vendors_with_reason(request):
    """Custom view to reject vendors with a reason"""
    if request.method == 'POST':
        vendor_ids = request.POST.get('vendor_ids', '').split(',')
        rejection_reason = request.POST.get('rejection_reason', '')
        
        if not rejection_reason:
            messages.error(request, 'Rejection reason is required')
            return redirect(request.META.get('HTTP_REFERER', '/admin/market_place/ticketvendor/'))
        
        rejected_count = 0
        for vendor_id in vendor_ids:
            try:
                vendor = TicketVendor.objects.get(id=vendor_id, verification_status='pending')
                vendor.verification_status = 'rejected'
                vendor.is_verified = False
                vendor.rejection_reason = rejection_reason
                vendor.save()
                
                # TODO: Send rejection email with reason
                # send_vendor_rejection_email(vendor, rejection_reason)
                
                rejected_count += 1
            except TicketVendor.DoesNotExist:
                continue
        
        messages.success(request, f'Successfully rejected {rejected_count} vendor(s)')
        return redirect('/admin/market_place/ticketvendor/')
    
    # GET request - show rejection form
    vendor_ids = request.GET.get('ids', '')
    vendors = TicketVendor.objects.filter(
        id__in=[int(x) for x in vendor_ids.split(',') if x],
        verification_status='pending'
    )
    
    return render(request, 'admin/market_place/reject_vendors.html', {
        'vendors': vendors,
        'vendor_ids': vendor_ids,
        'title': 'Reject Vendor Verification'
    })