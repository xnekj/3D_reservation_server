from django.contrib.auth.decorators import user_passes_test

def role_required(roles):
    def decorator(view_func):
        actual_decorator = user_passes_test(
            lambda u: u.is_authenticated and u.role in roles
        )
        return actual_decorator(view_func)
    return decorator