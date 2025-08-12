from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from admin_panel.models import *
from django.forms import inlineformset_factory
from .models import Product, ProductVariant, GiftSet
from .forms import ProductForm, ProductVariantForm, GiftSetForm
from django.core.paginator import Paginator
from datetime import datetime
from django.template.loader import render_to_string
# Admin Login View
from admin_panel.decorators import admin_login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from .forms import ProductForm, CategoryForm, SubCategoryForm
from django.shortcuts import render
from admin_panel.models import Product, Category, Subcategory, Order, OrderItem

from django.template.loader import render_to_string
from django.http import JsonResponse, HttpResponse
from .models import Banner


from django.db.models import Q, Sum, Count
from django.utils.timezone import now
from datetime import timedelta

from user_panel.models import UserProfile  # adjust to your actual model
from django.db.models.functions import TruncWeek, TruncMonth
# views.py
from django.shortcuts import render, redirect
from django.db.models import Sum, F, DecimalField


# views.py


from django.shortcuts import render, redirect
from django.contrib import messages
from .models import AdminUser
from .forms import AdminLoginForm, AdminPasswordChangeForm

def admin_login_view(request):
    if request.session.get('admin_id'):
        return redirect('admin_dashboard')

    form = AdminLoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        name = form.cleaned_data['name']
        password = form.cleaned_data['password']
        try:
            admin = AdminUser.objects.get(name=name, password=password)
            request.session['admin_id'] = admin.id
            return redirect('admin_dashboard')
        except AdminUser.DoesNotExist:
            messages.error(request, "Invalid credentials")
    
    return render(request, 'admin_panel/login.html', {'form': form})


# def admin_dashboard_view(request):
#     admin_id = request.session.get('admin_id')
#     if not admin_id:
#         return redirect('admin_login')
#     admin = AdminUser.objects.get(id=admin_id)
#     return render(request, 'admin_dashboard.html', {'admin': admin})


def admin_logout_view(request):
    request.session.flush()
    return redirect('admin_login')


def change_admin_password_view(request):
    admin_id = request.session.get('admin_id')
    if not admin_id:
        return redirect('admin_login')

    form = AdminPasswordChangeForm(request.POST or None)
    admin = AdminUser.objects.get(id=admin_id)

    if request.method == 'POST' and form.is_valid():
        old = form.cleaned_data['old_password']
        new = form.cleaned_data['new_password']
        confirm = form.cleaned_data['confirm_password']

        if old != admin.password:
            messages.error(request, "Old password incorrect")
        elif new != confirm:
            messages.error(request, "New passwords do not match")
        else:
            admin.password = new
            admin.save()
            messages.success(request, "Password changed successfully")
            return redirect('admin_dashboard')

    return render(request, 'admin_panel/change_password.html', {'form': form, 'admin': admin})

@admin_login_required
def admin_dashboard(request):
    today = now()
    current_month = today.month
    current_year = today.year

    # SALES SECTION (already present)
    status_filter = Q(status__in=['AWB Assigned', 'Completed'])
    completed_orders = Q(shiprocket_tracking_status='Delivered')

    total_sales_amount = Order.objects.filter(status_filter).aggregate(total=Sum('total_price'))['total'] or 0
    total_sales_count = Order.objects.filter(status_filter).count()
    total_deliverd_orders = Order.objects.filter(completed_orders).count()

    this_month_sales = Order.objects.filter(
        status_filter,
        created_at__year=current_year,
        created_at__month=current_month
    ).aggregate(total=Sum('total_price'))['total'] or 0

    last_month = current_month - 1 if current_month > 1 else 12
    last_month_year = current_year if current_month > 1 else current_year - 1

    last_month_sales = Order.objects.filter(
        status_filter,
        created_at__year=last_month_year,
        created_at__month=last_month
    ).aggregate(total=Sum('total_price'))['total'] or 0

    # SALES PERCENT CHANGE
    if last_month_sales == 0:
        if this_month_sales > 0:
            percent_change = 100.0
            message = f"🔼 Sales increased by {percent_change:.1f}% from last month"
            alert_class = "alert-success"
        else:
            percent_change = 0.0
            message = "No change in sales from last month"
            alert_class = "alert-secondary"
    else:
        percent_change = ((this_month_sales - last_month_sales) / last_month_sales) * 100
        if percent_change > 0:
            message = f"🔼 Sales increased by {percent_change:.1f}% from last month"
            alert_class = "alert-success"
        elif percent_change < 0:
            message = f"🔻 Sales dropped by {abs(percent_change):.1f}% from last month"
            alert_class = "alert-danger"
        else:
            message = "Sales remained the same as last month"
            alert_class = "alert-secondary"

    # ✅ CUSTOMER COUNTS
    total_customers = UserProfile.objects.count()

    this_month_customers = UserProfile.objects.filter(
        created_at__year=current_year,
        created_at__month=current_month
    ).count()

    last_month_customers = UserProfile.objects.filter(
        created_at__year=last_month_year,
        created_at__month=last_month
    ).count()

    if last_month_customers == 0:
        if this_month_customers > 0:
            customer_change_msg = f"🔼 Customers increased by 100% from last month"
            customer_alert = "alert-success"
        else:
            customer_change_msg = "No change in customer signups"
            customer_alert = "alert-secondary"
    else:
        customer_percent_change = ((this_month_customers - last_month_customers) / last_month_customers) * 100
        if customer_percent_change > 0:
            customer_change_msg = f"🔼 Customers increased by {customer_percent_change:.1f}% from last month"
            customer_alert = "alert-success"
        elif customer_percent_change < 0:
            customer_change_msg = f"🔻 Customers dropped by {abs(customer_percent_change):.1f}% from last month"
            customer_alert = "alert-danger"
        else:
            customer_change_msg = "Customer count unchanged from last month"
            customer_alert = "alert-secondary"

    weekly_orders = (
        Order.objects.filter(status__in=['Completed', 'AWB Assigned'])
        .annotate(week=TruncWeek('created_at'))
        .values('week')
        .annotate(count=Count('id'))
        .order_by('week')
    )
    weekly_labels = [entry['week'].strftime('%d %b') for entry in weekly_orders]
    weekly_counts = [entry['count'] for entry in weekly_orders]
    monthly_orders = (
        Order.objects.filter(status__in=['Completed', 'AWB Assigned'])
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    monthly_labels = [entry['month'].strftime('%b') for entry in monthly_orders]
    monthly_counts = [entry['count'] for entry in monthly_orders]
    product_filter = request.GET.get('filter', 'week')

    if product_filter == 'month':
        start_date = timezone.now() - timedelta(days=30)
    else:  # Default to week
        start_date = timezone.now() - timedelta(days=7)

    top_selling_products = (
        OrderItem.objects
        .filter(order__status__in=['AWB Assigned', 'Completed'], order__created_at__gte=start_date)
        .values('product__id', 'product__name')
        .annotate(total_quantity=Sum('quantity'))
        .order_by('-total_quantity')[:4]
    )

    max_quantity = top_selling_products[0]['total_quantity'] if top_selling_products else 1

    for product in top_selling_products:
        product['percentage'] = int((product['total_quantity'] / max_quantity) * 100)



    context = {
        # Sales context
        'total_sales_amount': total_sales_amount,
        'total_sales_count': total_sales_count,
        'sales_change_message': message,
        'alert_class': alert_class,

        # Customer context
        'total_customers': total_customers,
        'monthly_customers': this_month_customers,
        'customer_change_msg': customer_change_msg,
        'customer_alert': customer_alert,
        'total_deliverd_orders':total_deliverd_orders,
        'weekly_sales_data': json.dumps({'labels': weekly_labels, 'data': weekly_counts}),
        'monthly_sales_data': json.dumps({'labels': monthly_labels, 'data': monthly_counts}),
        'top_selling_products': top_selling_products,
        'product_filter': product_filter,
    }

    return render(request, 'admin_panel/admin_dashboard.html', context)

# views.py
from django.http import JsonResponse



# admin_panel/views.py





def get_chart_data(request):
    view = request.GET.get('view', 'month')
    year = int(request.GET.get('year', 2025))  # default to 2025 or current year

    status_filter = ['Completed', 'AWB Assigned']

    if view == 'week':
        orders = (
            Order.objects.filter(status__in=status_filter, created_at__year=year)
            .annotate(week=TruncWeek('created_at'))
            .values('week')
            .annotate(count=Count('id'))
            .order_by('week')
        )
        labels = [entry['week'].strftime('%d %b') for entry in orders]
        counts = [entry['count'] for entry in orders]

    else:  # month view
        orders = (
            Order.objects.filter(status__in=status_filter, created_at__year=year)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        labels = [entry['month'].strftime('%b') for entry in orders]
        counts = [entry['count'] for entry in orders]

    return JsonResponse({'labels': labels, 'data': counts})
# Manage Products (List, Add, Edit, Delete) ==============================================
# admin_panel/views.py
from django.shortcuts import render

def socket_test_view(request):
    return render(request, 'admin_panel/test_socket.html')

# @admin_login_required
@admin_login_required
def product_list(request):
    products = Product.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(subcategory__name__icontains=query)
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            products = products.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(products.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    
    
    product_form = ProductForm()
    
    ProductVariantFormSet = inlineformset_factory(Product, ProductVariant, form=ProductVariantForm, extra=1, can_delete=True)
    GiftSetFormSet = inlineformset_factory(Product, GiftSet, form=GiftSetForm, extra=1, can_delete=True)
    variant_formset = ProductVariantFormSet(prefix='variants')
    giftset_formset = GiftSetFormSet(prefix='giftsets')
    return render(request, 'admin_panel/product_list.html', {
        'page_obj': page_obj,
        'query': query,
        'selected_date': selected_date,
        "products": products,
        'product_form': product_form,
        'variant_formset': variant_formset,
        'giftset_formset': giftset_formset,
    })
@admin_login_required
def add_product(request):
    ProductVariantFormSet = inlineformset_factory(Product, ProductVariant, form=ProductVariantForm, extra=1, can_delete=True)
    GiftSetFormSet = inlineformset_factory(Product, GiftSet, form=GiftSetForm, extra=1, can_delete=True)

    if request.method == 'POST':
        product_form = ProductForm(request.POST, request.FILES)
        variant_formset = ProductVariantFormSet(request.POST, request.FILES, prefix='variants')
        giftset_formset = GiftSetFormSet(request.POST, request.FILES, prefix='giftsets')
        
        if product_form.is_valid() and variant_formset.is_valid() and giftset_formset.is_valid():
            product = product_form.save()
            variant_formset.instance = product
            variant_formset.save()
            giftset_formset.instance = product
            giftset_formset.save()
            return JsonResponse({'success': True})
        else:
            # Gather form errors
            errors = {
                'product_form_errors': product_form.errors,
                'variant_formset_errors': variant_formset.errors,
                'giftset_formset_errors': giftset_formset.errors,
            }
            return JsonResponse({'success': False, 'errors': errors}, status=400)

    else:
        # Optional: If you want to load the empty form in AJAX
        return JsonResponse({'error': 'Invalid request method.'}, status=400)


# views.py
def update_product(request, pk):
    product = get_object_or_404(Product, pk=pk)

    ProductVariantFormSet = inlineformset_factory(Product, ProductVariant, form=ProductVariantForm, extra=0, can_delete=True)
    GiftSetFormSet = inlineformset_factory(Product, GiftSet, form=GiftSetForm, extra=0, can_delete=True)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        variant_formset = ProductVariantFormSet(request.POST, request.FILES, instance=product)
        giftset_formset = GiftSetFormSet(request.POST, request.FILES, instance=product)

        # Allow empty unmodified forms
        for f in variant_formset.forms:
            if not f.has_changed():
                f.empty_permitted = True
        for f in giftset_formset.forms:
            if not f.has_changed():
                f.empty_permitted = True

        if form.is_valid() and variant_formset.is_valid() and giftset_formset.is_valid():
            form.save()
            variant_formset.save()
            giftset_formset.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({
                'success': False,
                'errors': {
                    'form': form.errors,
                    'variant_formset': [f.errors for f in variant_formset],
                    'giftset_formset': [f.errors for f in giftset_formset],
                }
            })

    else:
        form = ProductForm(instance=product)
        variant_formset = ProductVariantFormSet(instance=product)
        giftset_formset = GiftSetFormSet(instance=product)

        return render(request, 'admin_panel/product_form.html', {
            'form': form,
            'variant_formset': variant_formset,
            'giftset_formset': giftset_formset,
            'product': product,
        })



def delete_product(request, pk):
    if request.method == "POST":
        try:
            Product.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Product.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Product not found'}, status=404)
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request'}, status=405)
@admin_login_required    
def view_varaints(request):
    variants = ProductVariant.objects.select_related('product').all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        variants = variants.filter(
            Q(bottle_type__icontains=query)|
            Q(size__icontains=query)|
            Q(stock__icontains=query)

           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            variants = variants.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(variants.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Products without variants and giftsets

    return render(request, 'admin_panel/product_variants.html', {
        'variants': variants,'page_obj': page_obj,'query': query,
        'selected_date': selected_date
        
    })
@admin_login_required
def view_giftsets(request):
    giftsets = GiftSet.objects.select_related('product').all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        giftsets = giftsets.filter(
            Q(set_name__icontains=query)|
            Q(price__icontains=query)|
            Q(stock__icontains=query)

           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            giftsets = giftsets.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(giftsets.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # Produc
    return render(request, 'admin_panel/product_giftsets.html', {
       
        'giftsets': giftsets,'page_obj': page_obj,'query': query,
    })


# Manage Categories  =============================================
from .decorators import admin_login_required

@admin_login_required
def category_list(request):
    from .forms import CategoryForm
    categories = Category.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        categories = categories.filter(
            Q(name__icontains=query)
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            categories = categories.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(categories.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = CategoryForm()
    
    return render(request, 'admin_panel/category.html', {'categories': categories, 'form': form,'page_obj': page_obj,'query': query,
        'selected_date': selected_date,})



@admin_login_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save()
            return JsonResponse({
                'success': True,
                'id': category.id,
                'name': category.name,
                'banner_url': category.banner.url if category.banner else '',
                'gif_url': category.gif_file.url if category.gif_file else '',
                'created_at': category.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)




def edit_category(request, pk):
    try:
        category = Category.objects.get(pk=pk)
    except Category.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            category = form.save()
            return JsonResponse({
                'success': True,
                'id': category.id,
                'name': category.name,
                'banner_url': category.banner.url if category.banner else '',
                'gif_url': category.gif_file.url if category.gif_file else '',
                'created_at': category.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = CategoryForm(instance=category)
        html = render_to_string('admin_panel/category_form.html', {'form': form, 'category': category}, request)
        return HttpResponse(html)


@admin_login_required
def delete_category(request, pk):
    if request.method == "POST":
        try:
            Category.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Category.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Category not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)



# Manage Subcategories =====================================================
@admin_login_required
def subcategory_list(request):
    subcategories = Subcategory.objects.select_related('category').all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        subcategories = subcategories.filter(
            Q(name__icontains=query)
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            subcategories = subcategories.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(subcategories.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    form = SubCategoryForm()
    
    return render(request, 'admin_panel/subcategory_list.html', {
        'subcategories': subcategories,
        'page_obj': page_obj,
        'query': query,
        'selected_date': selected_date,
        'form': form,
    })
@admin_login_required
def add_subcategory(request):
    if request.method == 'POST':
        form = SubCategoryForm(request.POST,request.FILES)
        if form.is_valid():
            subcategory=form.save()
            return JsonResponse({
                'success': True,
                'id': subcategory.id,
                'name': subcategory.name,
                'category_id': subcategory.category.id,
                'category_name': subcategory.category.name,
                'banner_url': subcategory.banner.url if subcategory.banner else '',
                'image_url': subcategory.sub_image.url if subcategory.sub_image else '',
                'created_at': subcategory.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

@admin_login_required
def edit_subcategory(request, pk):
    try:
        subcategory = Subcategory.objects.get(pk=pk)
    except Subcategory.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = SubCategoryForm(request.POST, request.FILES, instance=subcategory)
        if form.is_valid():
            subcategory = form.save()
            return JsonResponse({
                'success': True,
                'id': subcategory.id,
                'name': subcategory.name,
                'category_id': subcategory.category.id,
                'category_name': subcategory.category.name,
                'banner_url': subcategory.banner.url if subcategory.banner else '',
                'image_url': subcategory.sub_image.url if subcategory.sub_image else '',
                'created_at': subcategory.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    # GET request
    categories = Category.objects.all()
    html = render_to_string(
        'admin_panel/subcategory_form.html',
        {
            'form': SubCategoryForm(instance=subcategory),
            'subcategory': subcategory,
            'categories': categories,  # 👈 Important!
        },
        request
    )
    return HttpResponse(html)

    
@admin_login_required
def delete_subcategory(request, pk):
    if request.method == "POST":
        try:
            Subcategory.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Subcategory.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'subCategory not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)
#=============================================================================================
from admin_panel.forms import *
@admin_login_required
def flavor_list(request):
    flavors = Flavour.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        flavors = flavors.filter(
            Q(name__icontains=query)
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            flavors = flavors.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(flavors.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = FlavourForm()
    
    return render(request, 'admin_panel/flavor_list.html', {'flavors': flavors, 'form': form,'page_obj': page_obj,'query': query,
        'selected_date': selected_date,})



@admin_login_required
def add_flavor(request):
    if request.method == 'POST':
        form = FlavourForm(request.POST, request.FILES)
        if form.is_valid():
            flavor = form.save()
            return JsonResponse({
                'success': True,
                'id': flavor.id,
                'name': flavor.name,
                'image': flavor.image.url if flavor.image else '',
                'created_at': flavor.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

def edit_flavor(request, pk):
    try:
        flavor = Flavour.objects.get(pk=pk)
    except Flavour.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = FlavourForm(request.POST, request.FILES, instance=flavor)
        if form.is_valid():
            flavor = form.save()
            return JsonResponse({
                'success': True,
                'id': flavor.id,
                'name': flavor.name,
                'image': flavor.image.url if flavor.image else '',
                'created_at': flavor.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = FlavourForm(instance=flavor)
        html = render_to_string('admin_panel/flavor_form.html', {'form': form, 'flavor': flavor}, request)
        return HttpResponse(html)

def delete_flavor(request, pk):
    if request.method == "POST":
        try:
            Flavour.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Flavour.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Flavour not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)


# ===========================================================================================================
from admin_panel.forms import *
@admin_login_required
def banner_list(request):
    banners = Banner.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        banners = banners.filter(
            Q(title__icontains=query)
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            banners = banners.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(banners.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = BannerForm()
    
    return render(request, 'admin_panel/banner_list.html', {'banners': banners, 'form': form,'page_obj': page_obj,'query': query,
        'selected_date': selected_date,})



@admin_login_required
def add_banner(request):
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = form.save()
            return JsonResponse({
                'success': True,
                'id': banner.id,
                'title': banner.title,
                'section': banner.get_section_display(),
                'banner_image': banner.banner_image.url if banner.banner_image else '',
                'created_at': banner.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)



def edit_banner(request, pk):
    try:
        banner = Banner.objects.get(pk=pk)
    except Banner.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            banner = form.save()
            return JsonResponse({
                'success': True,
                'id': banner.id,
                'title': banner.title,
                'section': banner.get_section_display(),
                'banner_image': banner.banner_image.url if banner.banner_image else '',
                'created_at': banner.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = BannerForm(instance=banner)
        html = render_to_string('admin_panel/banner_form.html', {'form': form, 'banner': banner}, request)
        return HttpResponse(html)


def delete_banner(request, pk):
    if request.method == "POST":
        try:
            Banner.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Banner.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Banner not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)
# ======================================================================================================

@admin_login_required
def festival_list(request):
    festivals = PremiumFestiveOffer.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        festivals = festivals.filter(
            Q(offer_name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(subcategory__name__icontains=query) 
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            festivals = festivals.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(festivals.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = PremiumFestiveOfferForm()
    
    return render(request, 'admin_panel/festival_list.html', {'festivals': festivals, 'form': form,'page_obj': page_obj,'query': query,
        'selected_date': selected_date,})




@admin_login_required

def add_festival(request):
    if request.method == 'POST':
        form = PremiumFestiveOfferForm(request.POST)
        if form.is_valid():
            festival = form.save(commit=False)  # save main object only
            festival.save()                     # now PK exists
            form.save_m2m()                     # save M2M relationships

            return JsonResponse({
                'success': True,
                'id': festival.id,
                'offer_name': festival.offer_name,
                'category': ", ".join(c.name for c in festival.category.all()),
                'subcategory': ", ".join(s.name for s in festival.subcategory.all()),
                'size': festival.size if festival.size else '',
                'premium_festival': festival.premium_festival,
                'percentage': float(festival.percentage or 0),
                'code': festival.code or '',
                'start_date': festival.start_date.strftime("%Y-%m-%d %H:%M") if festival.start_date else '',
                'end_date': festival.end_date.strftime("%Y-%m-%d %H:%M") if festival.end_date else '',
                'created_at': festival.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def edit_festival(request, pk):
    try:
        festival = PremiumFestiveOffer.objects.get(pk=pk)
    except PremiumFestiveOffer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = PremiumFestiveOfferForm(request.POST, request.FILES, instance=festival)
        if form.is_valid():
            festival = form.save()
            return JsonResponse({
                'success': True,
                'id': festival.id,
                'offer_name': festival.offer_name,
                'premium_festival': festival.premium_festival,
                'percentage': float(festival.percentage or 0),
                'category': ", ".join(c.name for c in festival.category.all()),
                'subcategory': ", ".join(s.name for s in festival.subcategory.all()),
                'code': festival.code or '',
                'start_date': festival.start_date.strftime("%Y-%m-%d %H:%M") if festival.start_date else '',
                'end_date': festival.end_date.strftime("%Y-%m-%d %H:%M") if festival.end_date else '',
                'created_at': festival.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = PremiumFestiveOfferForm(instance=festival)
        html = render_to_string('admin_panel/festival_form.html', {'form': form, 'festival': festival}, request)
        return HttpResponse(html)


def delete_festival(request, pk):
    if request.method == "POST":
        try:
            PremiumFestiveOffer.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except PremiumFestiveOffer.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Banner not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)

# =============================================================================================

@admin_login_required
def coupon_list(request):
    coupons = Coupon.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        coupons = coupons.filter(
            Q(code__icontains=query) |
            Q(discount__icontains=query) |
            Q(required_amount__icontains=query) 
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            coupons = coupons.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(coupons.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = CouponForm()
    
    return render(request, 'admin_panel/coupon_list.html', {'coupons': coupons, 'form': form,'page_obj': page_obj,'query': query,
        'selected_date': selected_date,})



@admin_login_required

def add_coupon(request):
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)  # save main object only
            coupon.save()                     # now PK exists

            return JsonResponse({
                'success': True,
                'id': coupon.id,
                'code': coupon.code or '',
                'discount': float(coupon.discount or 0),
                'required_amount': float(coupon.required_amount or 0),
                'is_active':coupon.is_active,
                'created_at': coupon.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


def edit_coupon(request, pk):
    try:
        coupon = Coupon.objects.get(pk=pk)
    except Coupon.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = CouponForm(request.POST, request.FILES, instance=coupon)
        if form.is_valid():
            coupon = form.save()
            return JsonResponse({
                'success': True,
                'id': coupon.id,
                'code': coupon.code or '',
                'discount': float(coupon.discount or 0),
                'required_amount': float(coupon.required_amount or 0),
                'is_active':coupon.is_active,

                'created_at': coupon.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = CouponForm(instance=coupon)
        html = render_to_string('admin_panel/coupon_form.html', {'form': form, 'coupon': coupon}, request)
        return HttpResponse(html)


def delete_coupon(request, pk):
    if request.method == "POST":
        try:
            Coupon.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Coupon.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Banner not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)

# ======================================================================================================
from .models import Product  # import if not already

@admin_login_required
def product_video_list(request):
    videos = ProductVideo.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')

    if query:
        videos = videos.filter(
            Q(related_products__name__icontains=query) |
            Q(title__icontains=query) 
        )

    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            videos = videos.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(videos.order_by('-id'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = ProductVideoForm()
    products = Product.objects.all()  # ✅ Fetch products

    return render(request, 'admin_panel/video_list.html', {
        'videos': videos,
        'form': form,
        'products': products,  # ✅ Add this line
        'page_obj': page_obj,
        'query': query,
        'selected_date': selected_date,
    })


@admin_login_required
def add_product_video(request):
    if request.method == 'POST':
        form = ProductVideoForm(request.POST,request.FILES)
        if form.is_valid():
            video = form.save(commit=False)  # save main object only
            video.save()                     # now PK exists
            form.save_m2m()                     # save M2M relationships

            return JsonResponse({
                'success': True,
                'id': video.id,
                'video': video.video.url if video.video else '',

                'title': video.title,
                'related_products': ", ".join(c.name for c in video.related_products.all()),
                
                'created_at': video.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)



def edit_product_video(request, pk):
    try:
        video = ProductVideo.objects.get(pk=pk)
    except ProductVideo.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = ProductVideoForm(request.POST, request.FILES, instance=video)
        if form.is_valid():
            video = form.save()
            return JsonResponse({
                'success': True,
                'id': video.id,
                'video': video.video.url if video.video else '',

                'title': video.title,
                'related_products': ", ".join(c.name for c in video.related_products.all()),
                
                'created_at': video.created_at.strftime("%Y-%m-%d %H:%M"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    else:
        form = ProductVideoForm(instance=video)
        products = Product.objects.all()  # ✅ Fetch all products
        html = render_to_string(
        'admin_panel/video_form.html',
        {'form': form, 'video': video, 'products': products},  # ✅ Include products
        request
    )        
        return HttpResponse(html)



def delete_product_video(request, pk):
    if request.method == "POST":
        try:
            ProductVideo.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except ProductVideo.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Banner not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)
    

#  =======================  ======================================
@admin_login_required

def Payment_view(request):
    details=Payment.objects.all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        details = details.filter(
            Q(transaction_id__icontains=query) |

            Q(payment_method__icontains=query) |
            Q(status__icontains=query)
        )
    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            details = details.filter(created_at__date=date_obj)
        except ValueError:
            pass
    paginator = Paginator(details.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'admin_panel/payment_list.html', {'details': details, 'page_obj': page_obj, 'query': query, 'selected_date': selected_date})

# ==========================================================================================
@admin_login_required

def review_list(request):
    reviews = Review.objects.select_related('product').all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')
    if query:
        reviews = reviews.filter(
            Q(rating__icontains=query)
           
        )

    # Filter by created_at date
    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            reviews = reviews.filter(created_at__date=date_obj)
        except ValueError:
            pass

    paginator = Paginator(reviews.order_by('-id'), 10)  # 10 products per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    form = ReviewForm()
    
    return render(request, 'admin_panel/review_list.html', {
        'reviews': reviews,
        'page_obj': page_obj,
        'query': query,
        'selected_date': selected_date,
        'form': form,
    })


@admin_login_required

def add_review(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save()
            return JsonResponse({
                'success': True,
                'id': review.id,
                'review_text': review.review_text,
                'product_id': review.product.id,
                'product_name': review.product.name,
                'rating': review.rating,
                'created_at': review.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)



def edit_review(request, pk):
    try:
        review = Review.objects.get(pk=pk)
    except Review.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)

    if request.method == 'POST':
        form = ReviewForm(request.POST, request.FILES, instance=review)
        if form.is_valid():
            review = form.save()
            return JsonResponse({
                 'success': True,
                'id': review.id,
                'review_text': review.review_text,
                'product_id': review.product.id,
                'product_name': review.product.name,
                'rating': review.rating,
                'created_at': review.created_at.strftime("%Y-%m-%d"),
            })
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    # GET request
    reviews = Product.objects.all()
    html = render_to_string(
        'admin_panel/rating_form.html',
        {
            'form': ReviewForm(instance=review),
            'review': review,
            'reviews': reviews,  # 👈 Important!
        },
        request
    )
    return HttpResponse(html)

    

def delete_review(request, pk):
    if request.method == "POST":
        try:
            Review.objects.get(pk=pk).delete()
            return JsonResponse({'success': True})
        except Review.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'subCategory not found'}, status=404)
    else:
        # For GET requests, return a confirmation page or a simple response
        return HttpResponse('Delete via POST only.', status=405)
 
# =======================================================================================================
from django.db.models import Count, Sum, Max
from user_panel.models import AddressModel
@admin_login_required

def users_list(request):
    profiles =AddressModel.objects.select_related('user').all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')

    if query:
        profiles = profiles.filter(
            Q(name__icontains=query) | Q(mobile__icontains=query)
        )

    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            profiles = profiles.filter(created_at__date=date_obj)
        except ValueError:
            pass

    # Pagination
    paginator = Paginator(profiles.order_by('-id'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Attach purchase info
    for profile in page_obj:
        

        orders = Order.objects.filter(user=profile.user, status='Completed')
        agg = orders.aggregate(
            total_orders=Count('id'),
            total_spent=Sum('total_price'),
            last_purchase=Max('created_at')
)
        profile.total_orders = agg['total_orders'] or 0
        profile.total_spent = agg['total_spent'] or 0
        profile.last_purchase = agg['last_purchase']
        print(f"User: {profile.user}, Orders: {orders.count()}, Spent: {profile.total_spent}, Last: {profile.last_purchase}")

    return render(request, 'admin_panel/users_list.html', {
        'page_obj': page_obj,
        'query': query,
        'selected_date': selected_date,
    })

from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
def block_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        user.is_active = False
        user.save()
        messages.success(request, f"{user.username} has been blocked.")
        return redirect(request.META.get('HTTP_REFERER', '/'))



# ===================================================================================================== 

@admin_login_required

def orders_list(request):
    orders = Order.objects.prefetch_related('items', 'user').all()
    query = request.GET.get('q', '')
    selected_date = request.GET.get('date', '')

    if query:
        orders = orders.filter(
            Q(user__username__icontains=query) |
            Q(address__Name__icontains=query) |
            Q(id__icontains=query) |
            Q(address__MobileNumber__icontains=query) |
            Q(shiprocket_tracking_status__icontains=query) |
            Q(total_price__icontains=query)
        )

    if selected_date:
        try:
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            orders = orders.filter(created_at__date=date_obj)
        except ValueError:
            pass

    # Paginate
    paginator = Paginator(orders.order_by('-id'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Now annotate only the paginated orders
    for order in page_obj.object_list:
        for item in order.items.all():
            # Convert selected_flavours string to actual names
            if item.selected_flavours:
                flavour_ids = [int(fid) for fid in item.selected_flavours.split(',') if fid.isdigit()]
                flavours_qs = Flavour.objects.filter(id__in=flavour_ids)
                item.flavour_names = ', '.join(f.name for f in flavours_qs)
            else:
                item.flavour_names = ''

        # Sum up total discount for this order
        order.total_discount = sum(item.discount_amount or 0 for item in order.items.all())

    return render(request, 'admin_panel/orders_list.html', {
        'orders': page_obj.object_list,
        'page_obj': page_obj,
        'query': query,
        'selected_date': selected_date,
    })




#shipping ===================================================

from .utils import get_shiprocket_token

def my_view(request):
    token = get_shiprocket_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    # Continue using the token for any Shiprocket API call...
from django.http import JsonResponse
from .utils import get_shiprocket_token,check_shiprocket_service

def test_token(request):
    try:
        token = get_shiprocket_token()
        return JsonResponse({"token": token})
    except Exception as e:
        return JsonResponse({"error": str(e)})
    
def get_best_courier_view(request, address_id):
    result = check_shiprocket_service(request.user, address_id)
    return JsonResponse(result)

# subscriptions/views.py

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from admin_panel.models import PushSubscription
import json
from django.db.models import Avg

@csrf_exempt
def save_subscription(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user = request.user

        PushSubscription.objects.update_or_create(
            user=user,
            defaults={
                'endpoint': data.get('endpoint'),
                'keys': data.get('keys')
            }
        )
        return JsonResponse({'status': 'saved'})


from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.timezone import now
from user_panel.models import HelpQuery  # Assuming your HelpQuery is in user_panel.models


def admin_help_query_list(request):
    status_filter = request.GET.get('status')
    if status_filter:
        queries = HelpQuery.objects.filter(status=status_filter).order_by('-created_at')
    else:
        queries = HelpQuery.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/help_query_list.html', {'queries': queries})


def admin_help_query_reply(request, query_id):
    query = get_object_or_404(HelpQuery, id=query_id)
    if request.method == 'POST':
        response_text = request.POST.get('response')
        if response_text.strip():
            query.admin_reply = f"{response_text} (Replied on {now().strftime('%d-%m-%Y %H:%M')})"
            query.status = 'Solved'
            query.save()
            messages.success(request, "Reply sent successfully!")
        return redirect('admin_help_query_list')
    return render(request, 'admin_panel/help_query_reply.html', {'query': query})
