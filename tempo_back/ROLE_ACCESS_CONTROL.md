# Role-Based Access Control Implementation

## Overview
Implemented comprehensive role-based access control for Lipaidox backend with three user roles:
- **fan**: Content consumers (default)
- **creator**: Content creators with monetization features  
- **admin**: Platform administrators

## Key Components

### 1. Permission System (`lipaidox/auth/permissions.py`)
- Role validation decorators: `@require_creator`, `@require_admin`, `@require_any_role`
- Permission utilities: `RolePermissions` class with feature-specific checks
- Automatic authentication and role validation

### 2. Payment System Architecture

#### **Creator Payment Methods** (PAYOUTS)
- **Purpose**: For creators to receive earnings
- **Access**: Creator-only
- **Features**: Bank transfers, mobile money, card payouts
- **Models**: `PaymentMethod` (creator-focused)

#### **Customer Payments** (PURCHASES)
- **Purpose**: For fans/customers to pay for content
- **Access**: Handled by separate module
- **Note**: Customer payment functionality is managed by an external payment module

### 3. Protected Endpoints

**Creator-only features:**
- Creator payment methods (for receiving payouts)
- Monetization settings
- KYC verification
- Content creation/management
- Creator profile management
- Subscriber analytics

**Customer features (All authenticated users):**
- Content purchasing (handled by external module)
- Subscriptions
- Tips/donations

**Admin-only features:**
- User management (update/delete)
- KYC admin access
- Platform administration

### 4. Security Enhancements
- Role validation at GraphQL resolver level
- Ownership verification for content operations
- Admin-only admin user creation
- Middleware for request-level role context

## Usage Examples

```python
# Creator-only mutation (for payouts)
@strawberry.mutation
@require_creator
def add_bank_transfer_method(self, info, input):
    # Only creators can add payout methods

# Multi-role access
@strawberry.mutation
@require_any_role("fan", "creator", "admin")
def subscribe_to_creator(self, info):
    # All authenticated users can access

# Admin or creator access
@strawberry.field  
@require_creator_or_admin
def my_analytics(self, info):
    # Creators and admins can access
```

## Access Control Matrix

| Feature | Fan | Creator | Admin |
|---------|-----|---------|-------|
| View Content | ✅ | ✅ | ✅ |
| Subscribe | ✅ | ✅ | ✅ |
| Make Purchases | ✅* | ✅* | ✅* |
| Create Content | ❌ | ✅ | ✅ |
| Add Payout Methods | ❌ | ✅ | ✅ |
| Monetization Settings | ❌ | ✅ | ✅ |
| KYC | ❌ | ✅ | ✅ |
| User Management | ❌ | ❌ | ✅ |

*Handled by external payment module

## Security Benefits
- Role-based access control properly implemented
- Prevents fans from accessing creator features
- Maintains data ownership integrity
- Enables secure multi-tenant architecture
- Clean separation of payment concerns
