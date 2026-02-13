from django.db import models
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User



class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)

    def __str__(self):
        return self.user.username

class Client(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Bill(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    sales_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    bill_number = models.CharField(max_length=50)
    bill_date = models.DateField()
    due_date = models.DateField()
    total_amount = models.FloatField()
    paid_amount = models.FloatField(default=0)
    

    def pending_amount(self):
        return (self.total_amount or 0) - (self.paid_amount or 0)
    
    def overdue_days(self):
        today = timezone.localdate()
        if self.due_date < today:
            return (today - self.due_date).days
        return 0

    def status(self):
        today = timezone.localdate()
        pending = self.pending_amount()

        if pending <= 0:
            return "Paid"
        elif self.due_date < today:
            return "Overdue"
        elif self.paid_amount > 0:
            return "Partial"
        else:
            return "Pending"
        
    def update_paid_amount(self):
        total_paid = self.payments.aggregate(
            total=Sum('amount')
        )['total'] or 0
        self.paid_amount = total_paid
        self.save(update_fields=['paid_amount'])

    def __str__(self):
        return f"{self.bill_number} - {self.client.name}"


class Payment(models.Model):
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
    ]

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount = models.FloatField()
    payment_mode = models.CharField(max_length=15, choices=PAYMENT_CHOICES)
    cheque_number = models.CharField(max_length=50, blank=True, null=True)
    payment_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.bill.bill_number} - {self.amount} ({self.payment_mode})"
    
