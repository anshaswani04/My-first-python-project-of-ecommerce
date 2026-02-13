from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Bill, Payment, Client, Profile
from django.db.models import Sum, F
from io import BytesIO
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.http import HttpResponse
import requests
from django.contrib import messages


def send_whatsapp_message(phone, message):
    url = "http://localhost:3000/send-message"

    data = {
        "number": f"91{phone}",
        "message": message
    }

    try:
        response = requests.post(url, json=data)
        return response.json()
    except Exception as e:
        return {"error": str(e)}



def send_overdue_reminder(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)

    # 🟢 Client Message
    client_message = f"""
Hi {bill.client.name},

Your Bill No {bill.bill_number}
Amount: ₹{bill.pending_amount():.2f}
Overdue by {bill.overdue_days()} days.

Kindly arrange payment.

– Suhagan Creations, Thank You.
"""

    send_whatsapp_message(bill.client.phone, client_message)

    # 🟡 Sales Person Notification
    if bill.sales_person and hasattr(bill.sales_person, 'profile'):
        sales_phone = bill.sales_person.profile.phone

        sales_message = f"""
Alert 🚨

Client: {bill.client.name}
Bill No: {bill.bill_number}
Pending: ₹{bill.pending_amount():.2f}
Overdue: {bill.overdue_days()} days

Please follow up immediately.
"""

        send_whatsapp_message(sales_phone, sales_message)

    messages.success(request, "Reminder sent successfully!")

    return redirect('dashboard')



def collection_dashboard(request):
    today = timezone.localdate()

    todays_bills = Bill.objects.filter(
        due_date=today,
        paid_amount__lt=models.F('total_amount')
    )

    overdue_bills = Bill.objects.filter(
        due_date__lt=today,
        paid_amount__lt=models.F('total_amount')
    )

    future_bills = Bill.objects.filter(
         due_date__gt=today,
         paid_amount__lt=models.F('total_amount')
    ).order_by('due_date')

    total_pending = (
        Bill.objects
        .filter(paid_amount__lt=models.F('total_amount'))
        .aggregate(
            pending=models.Sum(models.F('total_amount') - models.F('paid_amount'))
        )['pending'] or 0
    )

    context = {
        'today': today,
        'todays_bills': todays_bills,
        'overdue_bills': overdue_bills,
        'future_bills': future_bills,
        'total_pending': total_pending
    }

    return render(request, 'sales/dashboard.html', context)


@require_POST
def mark_as_paid(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)

    paid_now = float(request.POST.get('paid_now', 0))

    #add partial payment
    bill.paid_amount = bill.paid_amount or 0
    bill.paid_amount += paid_now

    #safety check: do not exceed total
    if bill.paid_amount > bill.total_amount:
        bill.paid_amount = bill.total_amount

    bill.save()
    return redirect('dashboard')


def client_outstanding_summary(request):
    clients_summary = (
        Bill.objects
        .filter(paid_amount__lt=F('total_amount'))
        .values(
            'client__id',
            'client__name',
            'client__phone'
        )
        .annotate(
            total_pending=Sum(F('total_amount') - F('paid_amount'))
        )
        .order_by('-total_pending')
    )

    context = {
        'clients_summary': clients_summary
    }
    return render(request, 'sales/client_summary.html', context)

@require_POST
def mark_as_paid(request, bill_id):
    bill = get_object_or_404(Bill, id=bill_id)

    amount = float(request.POST.get('paid_now'))
    mode = request.POST.get('payment_mode')
    cheque_no = request.POST.get('cheque_number', '')

    # Create payment record
    Payment.objects.create(
        bill=bill,
        amount=amount,
        payment_mode=mode,
        cheque_number=cheque_no if mode == 'cheque' else None
    )

    # Update bill total paid
    bill.paid_amount += amount
    if bill.paid_amount > bill.total_amount:
        bill.paid_amount = bill.total_amount

    bill.save()
    return redirect('dashboard')

def client_bills(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    bills = Bill.objects.filter(client=client)

    context = {
        'client': client,
        'bills': bills
    }
    return render(request, 'sales/client_bills.html', context)

def client_statement(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    from_date = request.GET.get('from')
    to_date = request.GET.get('to')

    bills = Bill.objects.filter(client=client)

    # ✅ APPLY DATE FILTERS
    if from_date:
        bills = bills.filter(bill_date__gte=from_date)

    if to_date:
        bills = bills.filter(bill_date__lte=to_date)

    bills = bills.prefetch_related('payments').order_by('bill_date')

    total_billed = bills.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    total_paid = bills.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    context = {
        'client': client,
        'bills': bills,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'total_pending': total_billed - total_paid,
        'from_date': from_date,
        'to_date': to_date,
    }

    return render(request, 'sales/client_statement.html', context)



def client_statement_pdf(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    from_date = request.GET.get('from')
    to_date = request.GET.get('to')

    bills = Bill.objects.filter(client=client)

    if from_date:
        bills = bills.filter(bill_date__gte=from_date)

    if to_date:
        bills = bills.filter(bill_date__lte=to_date)

    bills = bills.prefetch_related('payments').order_by('bill_date')

    total_billed = bills.aggregate(
        total=Sum('total_amount')
    )['total'] or 0

    total_paid = bills.aggregate(
        total=Sum('paid_amount')
    )['total'] or 0

    template = get_template('sales/client_statement_pdf.html')

    html = template.render({
        'client': client,
        'bills': bills,
        'total_billed': total_billed,
        'total_paid': total_paid,
        'total_pending': total_billed - total_paid,
        'from_date': from_date,
        'to_date': to_date,
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{client.name}_statement.pdf"'
    )

    pisa.CreatePDF(
        src=BytesIO(html.encode('UTF-8')),
        dest=response
    )

    return response
