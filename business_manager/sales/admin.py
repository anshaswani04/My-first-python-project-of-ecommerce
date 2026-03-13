from django.contrib import admin
from datetime import date
from .models import Shop, Client, Bill, Payment, Profile


class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(owner=request.user)
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.owner = request.user
        super().save_model(request, obj, form, change)

admin.site.register(Shop, ShopAdmin)
admin.site.register(Profile)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(shop__owner=request.user)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "shop":
            kwargs["queryset"] = Shop.objects.filter(owner=request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(shop__owner=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "shop":
            kwargs["queryset"] = Shop.objects.filter(owner=request.user)

        if db_field.name == "client":
            kwargs["queryset"] = Client.objects.filter(shop__owner=request.user)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def pending_amount_display(self, obj):
        return obj.pending_amount()

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