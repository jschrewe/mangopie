from mongoengine import ReferenceField

from tastypie.bundle import Bundle
from tastypie.fields import ApiField, RelatedField, NOT_PROVIDED
from tastypie.exceptions import ApiFieldError

class ListFieldValue(object):
    def __init__(self, value):
        self.value = value

class ListField(ApiField):
    dehydrated_type = 'list'
    # TODO: Find out how to make a dynamic help text
    help_text = 'A list of different types.'
    
    def __init__(self, inner_field, **kwargs):
        super(ListField, self).__init__(**kwargs)

        inner_field.attribute = 'value'
        self.inner_field = inner_field

    def convert(self, items):
        return [self.inner_field.dehydrate(Bundle(obj=ListFieldValue(item))) for item in items]

class ReferenceList(RelatedField):
    is_m2m = True
    help_text = 'Many related resources. Can be either a list of URIs or list of individually nested resource data.'
        
    # dehydrate - prepare for serialization
    def dehydrate(self, bundle):
        list = getattr(bundle.obj, self.attribute)
        
        list_dehydrated = []
        
        for obj in list:
            obj_resource = self.get_related_resource(obj)
            obj_bundle = Bundle(obj=obj, request=bundle.request)
            list_dehydrated.append(self.dehydrate_related(obj_bundle, obj_resource))
        
        return list_dehydrated
    
    # hydrate - prepare to become a document
    def hydrate(self, bundle):
        pass
    
    def hydrate_m2m(self, bundle):
        if self.readonly:
            return None
        
        # if field data is not provided in the bundle and the object
        # has data, we are most likely dealing with an update.
        # In that case set the data on the bundle and proceed like
        # it was provided. This is rather inefficient but keeps 
        # complexity limited. 
        if bundle.data.get(self.instance_name) is None and \
                getattr(bundle.obj, self.attribute) != []:
            bundle.data[self.instance_name] = self.dehydrate(bundle)
        
        if bundle.data.get(self.instance_name) is None:
            if self.blank:
                return []
            elif self.null:
                return []
            else:
                raise ApiFieldError("The '%s' field has no data and doesn't allow a null value." % self.instance_name)
        
        list_hydrated = []
        
        for value in bundle.data.get(self.instance_name):
            if value is None:
                continue

            kwargs = {
                'request': bundle.request,
            }

            if self.related_name:
                kwargs['related_obj'] = bundle.obj
                kwargs['related_name'] = self.related_name

            list_hydrated.append(self.build_related_resource(value, **kwargs))

        return list_hydrated


class EmbeddedResourceField(ApiField):
    def __init__(self, resource_type, **kwargs):
        super(EmbeddedResourceField, self).__init__(**kwargs)
        self.resource_type = resource_type

    def dehydrate(self, bundle):
        doc = getattr(bundle.obj, self.attribute)
        return self.resource_type().full_dehydrate(doc)

        
        