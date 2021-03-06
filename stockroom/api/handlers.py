from django.db.models import Count
from django.http import HttpResponse
from piston.handler import BaseHandler
from piston.utils import validate, rc
from stockroom.models import ProductCategory, Product, StockItem, CartItem, Cart as CartModel
from stockroom.cart import Cart
from stockroom.forms import CartItemForm
from stockroom.utils import structure_products, structure_gallery, build_thumbnail_list

import logging

class CsrfExemptBaseHandler(BaseHandler):
    """
        handles request that have had csrfmiddlewaretoken inserted 
        automatically by django's CsrfViewMiddleware
        see: http://andrew.io/weblog/2010/01/django-piston-and-handling-csrf-tokens/
    """
    def flatten_dict(self, dct):
        if 'csrfmiddlewaretoken' in dct:
            dct = dct.copy()
            del dct['csrfmiddlewaretoken']
        return super(CsrfExemptBaseHandler, self).flatten_dict(dct)
            
class ProductCategoryHandler(BaseHandler):
    allowed_methods = ('GET',)
    model = ProductCategory
    
    def read(self, request, slug=None):
        if slug:
            try:
                category = ProductCategory.objects.select_related().get(active=True, slug=slug)
                children = []
                for child in category.children.all():
                    logging.debug(child)
                    children.append({child.slug : child})
                response = {'details' : category, 'children' : children, }
                
            except ProductCategory.DoesNotExist:
                response = None
            return response
            
        else:
            try:
                categories = ProductCategory.objects.filter(active=True, parent=None)
            except ProductCategory.DoesNotExist:
                categories = None
            return categories

class ProductHandler(BaseHandler):
    allowed_methods = ('GET',)
    exclude = (),
    model = Product
    
    def read(self, request, product_pk=None):
        if product_pk:
            try:
                product = Product.objects.select_related().get(pk=product_pk)   
                stock = StockItem.objects.filter(product=product)
                colors = []
                for s in stock:
                    colors.append(s.color)
                response = {
                    'product' : product,
                    'stock' : stock,
                    'colors' : colors,
                }
            except Product.DoesNotExist:
                response = None
            return response
            
        else: 
            try:
                products = Product.objects.select_related().all()
                response = structure_products(products)
                
            except Product.DoesNotExist:
                response = None
            return response

class StockHandler(BaseHandler):
    allwed_methods = ('GET',)
    exclude = ()
    model = StockItem
    
    def read(self, request, product_pk=None):
        if pk:
            try:
                stock = StockItem.objects.select_related().filter(product=product_pk)
            except StockItem.DoesNotExist:
                stock = None
            return stock

class CartHandler(CsrfExemptBaseHandler):
    allowed_methods = ('GET', 'PUT',)
    exclude = (),
    model = CartItem
        
    def read(self, request, pk=None):
        cart = Cart(request)
        cart_info = cart.summary()
    
        if pk:
            try:
                cart_item = CartItem.objects.get(pk=pk, cart=cart_info.pk)
            except CartItem.DoesNotExist:
                return rc.NOT_FOUND
            
            response = {
                'pk' : cart_item.pk,
                'item' : cart_item.stock_item,
                'quantity' : cart_item.quantity,
            }
            
        else:
            cart_items = []                
            for i in cart:
                item_gallery = ProductGallery.objects.get(product=i.stock_item.product, color=i.stock_item.color)                
                cart_items.append({
                    'product' : i.stock_item.product,
                    'package_count' : i.stock_item.package_count,
                    'color' : i.stock_item.color,
                    'measurement': i.stock_item.measurement,
                    'thumbnails' : build_thumbnail_list(item_gallery),
                })
        
            response = {
                'checked_out' : cart_info.checked_out,
                'created_on' : cart_info.created_on,
                'items' : cart_items,
            }
            
        return response
    
    
    @validate(CartItemForm, 'PUT')
    def update(self, request):
        try:
            item = StockItem.objects.get(
                color=request.form.cleaned_data['color'], 
                measurement=request.form.cleaned_data['measurement'], 
                product=request.form.cleaned_data['product'])
        except StockItem.DoesNotExist:
            return rc.NOT_FOUND
        
        quantity = request.form.cleaned_data['quantity']
        cart = Cart(request)
        cart.update(item, item.get_price(), quantity)
        cart_info = cart.summary()
        cart_items = []
        for i in cart:
            thumb = i.stock_item.product.get_thumb()
            cart_items.append({
                'product' : i.stock_item.product,
                'package_count' : i.stock_item.package_count,
                'quantity' : i.quantity,
                'unit_price' : i.stock_item.get_price(),
                'color' : i.stock_item.color,
                'measurement': i.stock_item.measurement,
                'thumbnail' : {
                    '80x80' : thumb.url_80x80,
                }
            })
                
        thumb = item.product.get_thumb()        
        response = {
            'checked_out' : cart_info.checked_out,
            'created_on' : cart_info.created_on,
            'items' : cart_items,
            'last_added' : {
                'product' : item.product,
                'package_count' : item.package_count,
                'quantity' : quantity,
                'unit_price' : item.get_price(),
                'color' : item.color,
                'measurement' : item.measurement,
                'thumbnail' : {
                    '80x80' : thumb.url_80x80,
                }
            }
        }
        return response
