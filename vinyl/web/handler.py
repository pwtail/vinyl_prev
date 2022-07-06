from django.core.handlers.wsgi import WSGIHandler


class VinylWSGIHandler(WSGIHandler):


    def resolve_request(self, request):
        """
        Retrieve/set the urlconf for the request. Return the view resolved,
        with its args and kwargs.
        """
        # Work out the resolver.
        if hasattr(request, "urlconf"):
            urlconf = request.urlconf
            set_urlconf(urlconf)
            resolver = get_resolver(urlconf)
        else:
            resolver = get_resolver()
        # Resolve the view, and assign the match object back to the request.
        resolver_match = resolver.resolve(request.path_info, request.method)
        request.resolver_match = resolver_match
        return resolver_match