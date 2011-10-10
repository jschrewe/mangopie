from django.utils.encoding import smart_unicode

from pymongo.objectid import ObjectId
from mongoengine import ReferenceField

from tastypie.bundle import Bundle
from tastypie.resources import Resource
from tastypie.fields import ApiField

class ListFieldValue(object):
    def __init__(self, value):
        self.value = value

class ListField(ApiField):
    def __init__(self, inner_field, **kwargs):
        super(ListField, self).__init__(**kwargs)

        inner_field.attribute = 'value'
        self.inner_field = inner_field

    def convert(self, items):
        #print type(bundle)
        #items = getattr(bundle.obj, self.attribute)
        return [self.inner_field.dehydrate(Bundle(obj=ListFieldValue(item))) for item in items]
    
    def hydrate(self, bundle):
        field = bundle.obj._fields[self.attribute]
        # ReferenceFields need a little more massage...
        if isinstance(field.field, ReferenceField):
            try:
                items = bundle.data[self.attribute]
                klass = field.field.document_type
                return [klass.objects().get(pk=item) for item in items]
            except KeyError:
                pass
        
        return super(ListField, self).hydrate(bundle)
        

class DictField(ApiField):
    pass

class EmbeddedResourceField(ApiField):
    def __init__(self, resource_type, **kwargs):
        super(EmbeddedResourceField, self).__init__(**kwargs)
        self.resource_type = resource_type

    def dehydrate(self, bundle):
        doc = getattr(bundle.obj, self.attribute)
        return self.resource_type().full_dehydrate(doc)
    
#class ReferenceField(ApiField):
#    dehydrated_type = 'string'
#    help_text = 'Unicode string document id. Example: "4e8b67e357a0205319000000"'
#
#    def convert(self, value):
#        if value is None:
#            return None
#        
#        return smart_unicode(value.__str__()) 
#    
#    def hydrate(self, bundle):
#        value = super(ReferenceField, self).hydrate(bundle)
#        if isinstance(value, basestring):
#            return ObjectId(value)
#        return value
        
        