from mongoengine import ReferenceField

from tastypie.bundle import Bundle
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
        return [self.inner_field.dehydrate(Bundle(obj=ListFieldValue(item))) for item in items]

    def hydrate(self, bundle):
        field = bundle.obj._fields[self.attribute]
        # ReferenceFields need a little more massage...
        # TODO: This is the crap way to do it.
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
