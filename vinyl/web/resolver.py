from functools import cached_property

from django.urls import URLResolver, URLPattern, ResolverMatch, Resolver404


class MyURLPattern(URLPattern):
    def resolve(self, path, method):
        if self.method == method:
            return super().resolve(path)


class MyURLResolver(URLResolver):

    @cached_property
    def url_patterns(self):
        patterns = super().url_patterns
        for p in patterns:
            if p.__class__ is URLResolver:
                p.__class__ = MyURLResolver
            elif p.__class__ is URLPattern:
                p.__class__ = MyURLPattern
        return patterns

    def resolve(self, path, method):
        path = str(path)  # path may be a reverse_lazy object
        tried = []
        match = self.pattern.match(path)
        if match:
            new_path, args, kwargs = match
            for pattern in self.url_patterns:
                try:
                    sub_match = pattern.resolve(new_path, method)
                except Resolver404 as e:
                    self._extend_tried(tried, pattern, e.args[0].get("tried"))
                else:
                    if sub_match:
                        # Merge captured arguments in match with submatch
                        sub_match_dict = {**kwargs, **self.default_kwargs}
                        # Update the sub_match_dict with the kwargs from the sub_match.
                        sub_match_dict.update(sub_match.kwargs)
                        # If there are *any* named groups, ignore all non-named groups.
                        # Otherwise, pass all non-named arguments as positional
                        # arguments.
                        sub_match_args = sub_match.args
                        if not sub_match_dict:
                            sub_match_args = args + sub_match.args
                        current_route = (
                            ""
                            if isinstance(pattern, URLPattern)
                            else str(pattern.pattern)
                        )
                        self._extend_tried(tried, pattern, sub_match.tried)
                        return ResolverMatch(
                            sub_match.func,
                            sub_match_args,
                            sub_match_dict,
                            sub_match.url_name,
                            [self.app_name] + sub_match.app_names,
                            [self.namespace] + sub_match.namespaces,
                            self._join_route(current_route, sub_match.route),
                            tried,
                            captured_kwargs=sub_match.captured_kwargs,
                            extra_kwargs={
                                **self.default_kwargs,
                                **sub_match.extra_kwargs,
                            },
                        )
                    tried.append([pattern])
            raise Resolver404({"tried": tried, "path": new_path})
        raise Resolver404({"path": path})
