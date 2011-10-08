import sys

from tastypie.authorization import Authorization

class DjangoAuthorization(Authorization):
    """
    Uses permission checking from ``django.contrib.auth`` to map ``POST``,
    ``PUT``, and ``DELETE`` to their equivalent django auth permissions.
    """
    def _app_and_module_for_klass(self, klass):
        module_name = klass.__name__.lower()
        
        model_module = sys.modules[klass.__module__]
        app_label = model_module.__name__.split('.')[-2]
        
        return (app_label, module_name)
    
    def is_authorized(self, request, object=None):
        # GET is always allowed
        if request.method == 'GET':
            return True

        klass = self.resource_meta.object_class

        # cannot check permissions if we don't know the model
        if not klass:
            return True

        permission_codes = {
            'POST': '%s.add_%s',
            'PUT': '%s.change_%s',
            'DELETE': '%s.delete_%s',
        }

        # cannot map request method to permission code name
        if request.method not in permission_codes:
            return True

        permission_code = permission_codes[request.method] % self._app_and_module_for_klass(klass)

        # user must be logged in to check permissions
        # authentication backend must set request.user
        if not hasattr(request, 'user'):
            return False

        return request.user.has_perm(permission_code)