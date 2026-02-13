from django.contrib import admin
from datetime import date
from .models import Client, Bill, Payment, Profile

admin.site.register(Profile)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = (
        'bill_number',
        'client',
        'sales_person',
        'total_amount',
        'paid_amount',
        'pending_amount_display',
        'due_date',
        'payment_status',
    )

    inlines = [PaymentInline]

    def pending_amount_display(self, obj):
        return obj.pending_amount

    pending_amount_display.short_description = "Pending Amount"

    def payment_status(self, obj):
        if obj.paid_amount >= obj.total_amount:
            return "Paid"
        elif obj.due_date < date.today():
            return "Overdue"
        elif obj.paid_amount > 0:
            return "Partial"
        return "Pending"

    payment_status.short_description = "Status"

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.update_paid_amount()
