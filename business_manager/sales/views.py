from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Bill, Payment, Client, Profile
from django.db.models import Sum, F
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from django.template.loader import get_template
from django.http import HttpResponse
import requests
from django.contrib import messages
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from html.parser import HTMLParser
import re


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

    # Create PDF using ReportLab
    doc = SimpleDocTemplate(response, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#000000'),
        spaceAfter=20,
    )
    story.append(Paragraph(f"Statement for {client.name}", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Client Details
    detail_style = styles['Normal']
    story.append(Paragraph(f"<b>Client Name:</b> {client.name}", detail_style))
    story.append(Paragraph(f"<b>Phone:</b> {client.phone}", detail_style))
    story.append(Paragraph(f"<b>Email:</b> {client.email or 'N/A'}", detail_style))
    if from_date or to_date:
        date_range = f"{from_date or 'Start'} to {to_date or 'End'}"
        story.append(Paragraph(f"<b>Period:</b> {date_range}", detail_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Bills Table
    table_data = [['Bill No', 'Date', 'Amount', 'Paid', 'Pending']]
    for bill in bills:
        table_data.append([
            str(bill.bill_number),
            bill.bill_date.strftime('%d-%m-%Y'),
            f"₹{bill.total_amount:.2f}",
            f"₹{bill.paid_amount:.2f}",
            f"₹{bill.pending_amount():.2f}",
        ])
    
    # Add totals row
    table_data.append(['TOTAL', '', f"₹{total_billed:.2f}", f"₹{total_paid:.2f}", f"₹{total_billed - total_paid:.2f}"])
    
    table = Table(table_data, colWidths=[1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E0E0E0')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)
    
    # Build PDF
    doc.build(story)
    return response
