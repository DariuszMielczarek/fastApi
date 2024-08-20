from client_management_package import hash_password, verify_password, pwd_context


def test_hash_password_should_return_given_password_hash():
    password = 'password123ABC'
    hashed_password = hash_password(password)
    assert pwd_context.verify(password, hashed_password)


def test_verify_password_should_return_true_when_passwords_are_the_same():
    password = 'password123ABC'
    hashed_password = pwd_context.hash(password)
    assert verify_password(password, hashed_password)


def test_verify_password_should_return_false_when_passwords_are_different():
    password = 'password123ABC'
    hashed_password = pwd_context.hash(password)
    assert not verify_password(password + '1', hashed_password)
