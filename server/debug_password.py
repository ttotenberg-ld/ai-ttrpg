from middleware.password_validator import validate_password_strength

result = validate_password_strength('StrongPassword123!')
print(f'Valid: {result.is_valid}')
print(f'Score: {result.score}')
print(f'Errors: {result.errors}')
print(f'Suggestions: {result.suggestions}')
print(f'Level: {result.strength_level}') 