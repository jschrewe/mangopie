from tastypie import fields as tasty_fields
from tastypie.bundle import Bundle
from tastypie.exceptions import TastypieError, NotFound
from tastypie.resources import Resource, DeclarativeMetaclass
from tastypie.utils import dict_strip_unicode_keys

from mongoengine import EmbeddedDocument
from mongoengine import fields as mongo_fields
from mongoengine.queryset import DoesNotExist

from mangopie import fields

FIELD_MAP = {
    mongo_fields.BooleanField: tasty_fields.BooleanField,
    mongo_fields.DateTimeField: tasty_fields.DateTimeField,
    mongo_fields.IntField: tasty_fields.IntegerField,
    mongo_fields.FloatField: tasty_fields.FloatField,
    mongo_fields.DictField: fields.DictField,
    mongo_fields.ListField: fields.ListField,
# Char Fields:
#  StringField, ObjectIdField, EmailField, URLField
# TODO
# 'ReferenceField',
# 'DecimalField', 'GenericReferenceField', 'FileField',
# 'BinaryField', , 'GeoPointField']
}

class DocumentDeclarativeMetaclass(DeclarativeMetaclass):
    def __new__(cls, name, bases, attrs):
        meta = attrs.get('Meta')

        if meta:
            if hasattr(meta, 'queryset') and not hasattr(meta, 'object_class'):
                setattr(meta, 'object_class', meta.queryset._document)

            if hasattr(meta, 'object_class') and not hasattr(meta, 'queryset'):
                if hasattr(meta.object_class, 'objects'):
                    setattr(meta, 'queryset', meta.object_class.objects.all())

            document_type = getattr(meta, 'object_class')

            if issubclass(document_type, EmbeddedDocument):
                if hasattr(meta, 'include_resource_uri'):
                    if getattr(meta, 'include_resource_uri'):
                        raise TastypieError("include_resource_uri cannot be True when the resource is an instance of EmbeddedDocument: %s" % document_type)
                else:
                    setattr(meta, 'include_resource_uri', False)

        new_class = super(DocumentDeclarativeMetaclass, cls).__new__(cls, name, bases, attrs)
        fields = getattr(new_class._meta, 'fields', [])
        excludes = getattr(new_class._meta, 'excludes', [])
        field_names = new_class.base_fields.keys()

        for field_name in field_names:
            if field_name == 'resource_uri':
                continue
            if field_name in new_class.declared_fields:
                continue
            if len(fields) and not field_name in fields:
                del(new_class.base_fields[field_name])
            if len(excludes) and field_name in excludes:
                del(new_class.base_fields[field_name])

        # Add in the new fields.
        new_class.base_fields.update(new_class.get_fields(fields, excludes))

        if getattr(new_class._meta, 'include_absolute_url', True):
            if not 'absolute_url' in new_class.base_fields:
                new_class.base_fields['absolute_url'] = tasty_fields.CharField(attribute='get_absolute_url', readonly=True)
        elif 'absolute_url' in new_class.base_fields and not 'absolute_url' in attrs:
            del(new_class.base_fields['absolute_url'])

        return new_class

class DocumentResource(Resource):
    """
    A subclass of ``Resource`` designed to work with mongoengine's ``Document``.

    This class will introspect a given ``Document`` and build a field list based
    on the fields found on the model (excluding relational fields).

    Given that it is aware of Django's ORM, it also handles the CRUD data
    operations of the resource.
    """
    __metaclass__ = DocumentDeclarativeMetaclass

    @classmethod
    def resource_for_document_type(cls, document_type):
        class Meta:
            object_class = document_type

        return DocumentDeclarativeMetaclass('%sResource' % document_type.__name__, (DocumentResource,), {'Meta': Meta})

    @classmethod
    def api_field_from_mongoengine_field(cls, f, default=tasty_fields.CharField):
        """
        Returns the field type that would likely be associated with each
        mongoengine type.
        """
        if isinstance(f, mongo_fields.ListField):
            inner_field, field_args = cls.api_field_from_mongoengine_field(f.field)
            return fields.ListField, {'inner_field': inner_field(**field_args)}
        elif isinstance(f, mongo_fields.EmbeddedDocumentField):
            return fields.EmbeddedResourceField, {'resource_type': cls.resource_for_document_type(f.document_type_obj)}
        else:
            while(f != type):
                if f in FIELD_MAP:
                    return FIELD_MAP[f], { }

                f = f.__class__

        return default, { }

    @classmethod
    def get_fields(cls, fields=None, excludes=None):
        """
        Given any explicit fields to include and fields to exclude, add
        additional fields based on the associated model.
        """
        final_fields = {}
        fields = fields or []
        excludes = excludes or []

        if not cls._meta.object_class:
            return final_fields

        for name, f in cls._meta.object_class._fields.iteritems():
            # If the field name is already present, skip
            if name in cls.base_fields:
                continue

            # If field is not present in explicit field listing, skip
            if fields and name not in fields:
                continue

            # If field is in exclude list, skip
            if excludes and name in excludes:
                continue

            api_field_class, kwargs = cls.api_field_from_mongoengine_field(f)

            kwargs.update({
              'attribute': name,
              'unique':    f.unique,
              'default':   f.default
            })

            if f.required is False:
                kwargs['null'] = True

            final_fields[name] = api_field_class(**kwargs)
            final_fields[name].instance_name = name

        return final_fields

    def _new_query(self):
        return self._meta.queryset.clone()

    def get_object_list(self, request):
        """
        An ORM-specific implementation of ``get_object_list``.

        Returns a queryset that may have been limited by authorization or other
        overrides.
        """
        base_object_list = self._new_query()

        # Limit it as needed.
        authed_object_list = self.apply_authorization_limits(request, base_object_list)

        return authed_object_list

    def build_filters(self, filters=None):
        """ Given a dictionary of filters, create the necessary ORM-level filters.

            Keys should be resource fields, **NOT** model fields.

            Valid values are either a list of Django filter types (i.e.
            ``['startswith', 'exact', 'lte']``), the ``ALL`` constant or the
            ``ALL_WITH_RELATIONS`` constant. """
        # At the declarative level:
        #     filtering = {
        #         'resource_field_name': ['exact', 'startswith', 'endswith', 'contains'],
        #         'resource_field_name_2': ['exact', 'gt', 'gte', 'lt', 'lte', 'range'],
        #         'resource_field_name_3': ALL,
        #         'resource_field_name_4': ALL_WITH_RELATIONS,
        #         ...
        #     }
        # Accepts the filters as a dict. None by default, meaning no filters.
        if filters is None:
            filters = {}

        qs_filters = {}

        LOOKUP_SEP = '__'
        QUERY_TERMS = ['ne', 'gt', 'gte', 'lt', 'lte', 'in', 'nin', 'mod', 'all', 'size', 'exists', 'not',
            'within_distance', 'within_spherical_distance', 'within_box', 'within_polygon', 'near',
            'near_sphere', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith',
            'exact', 'iexact', 'match']

        for filter_expr, value in filters.items():
            filter_bits = filter_expr.split(LOOKUP_SEP)
            field_name = filter_bits.pop(0)
            filter_type = 'exact'

            if not field_name in self.fields:
                # It's not a field we know about. Move along citizen.
                continue

            # Allow the use of positional searching on ListFields
            if (len(filter_bits) and filter_bits[-1] in QUERY_TERMS) or \
                    (len(filter_bits) and filter_bits[-1].isdigit() and \
                        isinstance(getattr(self._meta.object_class, field_name), mongo_fields.ListField)):
                filter_type = filter_bits.pop()

            lookup_bits = [field_name]

            # Split on ',' if not empty string and either an in or range filter. We also want to get the list
            # version of the value if the field in question is a ListField.
            if (filter_type in ('in', 'range') and len(value)) or \
                    isinstance(getattr(self._meta.object_class, field_name), mongo_fields.ListField):
                if hasattr(filters, 'getlist'):
                    if len(filters.getlist(filter_expr)) > 1:
                        value = filters.getlist(filter_expr)
                else:
                    value = value.split(',')

            db_field_name = LOOKUP_SEP.join(lookup_bits)
            qs_filter = "%s%s%s" % (db_field_name, LOOKUP_SEP, filter_type)
            qs_filters[qs_filter] = value

        return dict_strip_unicode_keys(qs_filters)


    def obj_get_list(self, request=None, **kwargs):
        """
        A ORM-specific implementation of ``obj_get_list``.

        Takes an optional ``request`` object, whose ``GET`` dictionary can be
        used to narrow the query.
        """
        filters = None

        if hasattr(request, 'GET'):
            filters = request.GET

        applicable_filters = self.build_filters(filters=filters)

        try:
            return self.get_object_list(request).filter(**applicable_filters)
        except ValueError, e:
            raise NotFound("Invalid resource lookup data provided (mismatched type).")

    def obj_get(self, request=None, **kwargs):
        """
        A ORM-specific implementation of ``obj_get``.

        Takes optional ``kwargs``, which are used to narrow the query to find
        the instance.
        """
        try:
            return self.get_object_list(request).get(**kwargs)
        except ValueError, e:
            raise NotFound("Invalid resource lookup data provided (mismatched type).")

    def obj_delete_list(self, request=None, **kwargs):
        """
        A ORM-specific implementation of ``obj_delete_list``.

        Takes optional ``kwargs``, which can be used to narrow the query.
        """
        self.get_object_list(request).filter(**kwargs).delete()

    def obj_delete(self, request=None, **kwargs):
        """
        A ORM-specific implementation of ``obj_delete``.

        Takes optional ``kwargs``, which are used to narrow the query to find
        the instance.
        """
        try:
            obj = self.get_object_list(request).get(**kwargs)
        except DoesNotExist:
            raise NotFound("A model instance matching the provided arguments could not be found.")

        obj.delete()

    def get_resource_uri(self, bundle_or_obj):
        """
        Handles generating a resource URI for a single resource.

        Uses the model's ``pk`` in order to create the URI.
        """
        kwargs = {
          'resource_name': self._meta.resource_name,
        }
        
        if isinstance(bundle_or_obj, Bundle):
            kwargs['pk'] = bundle_or_obj.obj.pk
        else:
            kwargs['pk'] = bundle_or_obj.pk

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url("api_dispatch_detail", kwargs=kwargs)
    
    def obj_create(self, bundle, request=None, **kwargs):
        bundle.obj = self._meta.object_class()
        
        for key, value in kwargs.items():
            setattr(bundle.obj, key, value)
            
        bundle = self.full_hydrate(bundle)
        bundle.obj.save()
        
        return bundle
    
    def obj_update(self, bundle, request=None, **kwargs):
        if not bundle.obj or not bundle.obj.pk:
            # Attempt to hydrate data from kwargs before doing a lookup for the object.
            # This step is needed so certain values (like datetime) will pass model validation.
            try:  
                bundle.obj = self.get_object_list(request)._document()
                bundle.data.update(kwargs)
                bundle = self.full_hydrate(bundle)
                lookup_kwargs = kwargs.copy()
                lookup_kwargs.update(dict(
                    (k, getattr(bundle.obj, k))
                    for k in kwargs.keys()
                    if getattr(bundle.obj, k) is not None))
            except:
                # if there is trouble hydrating the data, fall back to just
                # using kwargs by itself (usually it only contains a "pk" key
                # and this will work fine.
                lookup_kwargs = kwargs
            try:  
                bundle.obj = self.obj_get(request, **lookup_kwargs)
            except DoesNotExist:
                raise NotFound("A model instance matching the provided arguments could not be found.")

        bundle = self.full_hydrate(bundle)
        bundle.obj.save()

        return bundle
        
        
