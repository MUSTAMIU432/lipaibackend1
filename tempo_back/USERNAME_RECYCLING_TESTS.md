# GraphQL Username Recycling Test Guide

## 1. Check Username Availability

```graphql
query CheckUsernameAvailability {
  checkUsernameAvailability(username: "sophia")
}
```

**Expected Response:**
```json
{
  "data": {
    "checkUsernameAvailability": true
  }
}
```

## 2. Create Profile with Username

```graphql
mutation CreateProfile {
  createProfile(input: {
    username: "sophia"
    bio: "Test user bio"
  }) {
    id
    username
    bio
  }
}
```

**Expected Response:**
```json
{
  "data": {
    "createProfile": {
      "id": "uuid-here",
      "username": "sophia",
      "bio": "Test user bio"
    }
  }
}
```

## 3. Check Username Availability After Creation

```graphql
query CheckUsernameAvailability {
  checkUsernameAvailability(username: "sophia")
}
```

**Expected Response:**
```json
{
  "data": {
    "checkUsernameAvailability": false
  }
}
```

## 4. Update Username (This should release the old username)

```graphql
mutation UpdateProfile {
  updateProfile(input: {
    username: "sophia_tz"
    bio: "Updated bio"
  }) {
    id
    username
    bio
  }
}
```

**Expected Response:**
```json
{
  "data": {
    "updateProfile": {
      "id": "uuid-here",
      "username": "sophia_tz",
      "bio": "Updated bio"
    }
  }
}
```

## 5. Check if Old Username is Now Available

```graphql
query CheckUsernameAvailability {
  checkUsernameAvailability(username: "sophia")
}
```

**Expected Response (should be true now):**
```json
{
  "data": {
    "checkUsernameAvailability": true
  }
}
```

## 6. Check if New Username is Taken

```graphql
query CheckUsernameAvailability {
  checkUsernameAvailability(username: "sophia_tz")
}
```

**Expected Response:**
```json
{
  "data": {
    "checkUsernameAvailability": false
  }
}
```

## 7. Try to Create Another Profile with Old Username

```graphql
mutation CreateSecondProfile {
  createProfile(input: {
    username: "sophia"
    bio: "Second user with recycled username"
  }) {
    id
    username
    bio
  }
}
```

**Expected Response:**
```json
{
  "data": {
    "createSecondProfile": {
      "id": "new-uuid-here",
      "username": "sophia",
      "bio": "Second user with recycled username"
    }
  }
}
```

## 8. Error Cases

### Try to Take Already Used Username

```graphql
mutation TryTakenUsername {
  updateProfile(input: {
    username: "sophia_tz"  # This should fail
  }) {
    id
    username
  }
}
```

**Expected Error Response:**
```json
{
  "errors": [
    {
      "message": "Username already taken in this platform."
    }
  ]
}
```

### Try to Create Profile with Taken Username

```graphql
mutation CreateTakenUsername {
  createProfile(input: {
    username: "sophia_tz"
    bio: "Should fail"
  }) {
    id
    username
  }
}
```

**Expected Error Response:**
```json
{
  "errors": [
    {
      "message": "Username already taken in this platform."
    }
  ]
}
```

## 9. Test Multiple Username Changes

```graphql
# Change username multiple times
mutation ChangeUsername1 {
  updateProfile(input: {
    username: "sophia_2024"
  }) {
    username
  }
}

mutation ChangeUsername2 {
  updateProfile(input: {
    username: "sophia_final"
  }) {
    username
  }
}
```

## 10. Verify All Previous Usernames are Available

```graphql
query CheckAllPreviousUsernames {
  sophia: checkUsernameAvailability(username: "sophia")
  sophia_tz: checkUsernameAvailability(username: "sophia_tz")
  sophia_2024: checkUsernameAvailability(username: "sophia_2024")
  sophia_final: checkUsernameAvailability(username: "sophia_final")
}
```

**Expected Response:**
```json
{
  "data": {
    "sophia": true,
    "sophia_tz": true,
    "sophia_2024": true,
    "sophia_final": false
  }
}
```

## Testing Steps Summary:

1. ✅ Check availability of "sophia" (should be true)
2. ✅ Create profile with "sophia"
3. ✅ Check availability of "sophia" (should be false)
4. ✅ Update username to "sophia_tz"
5. ✅ Check availability of "sophia" (should be true - recycled!)
6. ✅ Check availability of "sophia_tz" (should be false)
7. ✅ Create new profile with "sophia" (should work)
8. ✅ Test error cases for taken usernames
9. ✅ Test multiple username changes
10. ✅ Verify all previous usernames become available

## GraphQL Playground Setup:

1. Open GraphQL Playground at `http://127.0.0.1:8000/graphql/`
2. Login first (if authentication is required)
3. Run the queries in order to test the complete flow

This will demonstrate the complete username recycling functionality!
