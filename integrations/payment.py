"""
Payment Processing Integration
Stripe integration for subscription and payment processing
"""

import stripe
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from database import get_db_connection
from logger_config import logger, audit_logger
from app_config import config


# Initialize Stripe
stripe.api_key = getattr(config, 'STRIPE_SECRET_KEY', 'sk_test_...')
stripe.api_version = '2023-10-16'


class PaymentManager:
    """Manages payment processing and subscriptions"""
    
    def __init__(self):
        self.webhook_secret = getattr(config, 'STRIPE_WEBHOOK_SECRET', '')
        
        # Define subscription plans
        self.plans = {
            'basic': {
                'name': 'Basic',
                'price_id': getattr(config, 'STRIPE_BASIC_PRICE_ID', 'price_basic'),
                'amount': 999,  # $9.99
                'currency': 'usd',
                'interval': 'month',
                'features': [
                    '100 QR codes per month',
                    'Basic analytics',
                    'Email support'
                ]
            },
            'pro': {
                'name': 'Professional',
                'price_id': getattr(config, 'STRIPE_PRO_PRICE_ID', 'price_pro'),
                'amount': 2999,  # $29.99
                'currency': 'usd',
                'interval': 'month',
                'features': [
                    'Unlimited QR codes',
                    'Advanced analytics',
                    'Priority support',
                    'Custom branding',
                    'API access'
                ]
            },
            'enterprise': {
                'name': 'Enterprise',
                'price_id': getattr(config, 'STRIPE_ENTERPRISE_PRICE_ID', 'price_enterprise'),
                'amount': 9999,  # $99.99
                'currency': 'usd',
                'interval': 'month',
                'features': [
                    'Everything in Pro',
                    'White-label solution',
                    'Dedicated support',
                    'Custom integrations',
                    'SLA guarantee'
                ]
            }
        }
    
    def create_checkout_session(self, user_id: int, plan_id: str, 
                              success_url: str = None, cancel_url: str = None) -> Dict[str, Any]:
        """Create Stripe checkout session for subscription"""
        
        try:
            if plan_id not in self.plans:
                return {'success': False, 'error': 'Invalid plan'}
            
            plan = self.plans[plan_id]
            
            # Get user info
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT username, email FROM users WHERE user_id = ?
            ''', (user_id,))
            
            user = cursor.fetchone()
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            username, email = user
            
            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                customer_email=email,
                line_items=[{
                    'price': plan['price_id'],
                    'quantity': 1,
                }],
                metadata={
                    'user_id': str(user_id),
                    'plan_id': plan_id,
                    'username': username
                },
                success_url=success_url or f"{config.BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url or f"{config.BASE_URL}/payment/cancel",
                allow_promotion_codes=True,
                billing_address_collection='required',
                customer_creation='always'
            )
            
            # Save session to database
            cursor.execute('''
                INSERT INTO payment_sessions (
                    session_id, user_id, plan_id, amount, currency,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                checkout_session.id,
                user_id,
                plan_id,
                plan['amount'],
                plan['currency'],
                'pending',
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            
            audit_logger.log_payment_initiated(user_id, checkout_session.id, plan_id, plan['amount'])
            
            return {
                'success': True,
                'session_id': checkout_session.id,
                'checkout_url': checkout_session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout session error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Payment session creation error: {e}")
            return {'success': False, 'error': 'Payment processing failed'}
    
    def create_customer_portal_session(self, user_id: int) -> Dict[str, Any]:
        """Create Stripe customer portal session"""
        
        try:
            # Get user's Stripe customer ID
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT stripe_customer_id FROM user_subscriptions 
                WHERE user_id = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result or not result[0]:
                return {'success': False, 'error': 'No active subscription found'}
            
            customer_id = result[0]
            
            # Create portal session
            portal_session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{config.BASE_URL}/account/subscription"
            )
            
            return {
                'success': True,
                'portal_url': portal_session.url
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe portal session error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Portal session creation error: {e}")
            return {'success': False, 'error': 'Failed to create portal session'}
    
    def process_webhook(self, payload: str, sig_header: str) -> Dict[str, Any]:
        """Process Stripe webhook events"""
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            
            event_type = event['type']
            event_data = event['data']['object']
            
            if event_type == 'checkout.session.completed':
                return self._handle_checkout_completed(event_data)
            
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(event_data)
            
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(event_data)
            
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_cancelled(event_data)
            
            else:
                logger.info(f"Unhandled webhook event: {event_type}")
                return {'success': True, 'message': 'Event received'}
                
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid webhook signature")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return {'success': False, 'error': 'Webhook processing failed'}
    
    def _handle_checkout_completed(self, session_data: Dict) -> Dict[str, Any]:
        """Handle successful checkout completion"""
        
        try:
            metadata = session_data.get('metadata', {})
            user_id = int(metadata.get('user_id'))
            plan_id = metadata.get('plan_id')
            customer_id = session_data.get('customer')
            subscription_id = session_data.get('subscription')
            
            # Update payment session
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE payment_sessions 
                SET status = 'completed', stripe_customer_id = ?, 
                    stripe_subscription_id = ?, completed_at = ?
                WHERE session_id = ?
            ''', (
                customer_id,
                subscription_id,
                datetime.now().isoformat(),
                session_data['id']
            ))
            
            # Create or update subscription record
            plan = self.plans[plan_id]
            
            cursor.execute('''
                INSERT OR REPLACE INTO user_subscriptions (
                    user_id, plan_id, stripe_customer_id, stripe_subscription_id,
                    status, amount, currency, interval, 
                    current_period_start, current_period_end,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                plan_id,
                customer_id,
                subscription_id,
                'active',
                plan['amount'],
                plan['currency'],
                plan['interval'],
                datetime.now().isoformat(),  # Will be updated with actual dates
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))
            
            # Update user role to premium
            cursor.execute('''
                UPDATE users SET role = 'premium' WHERE user_id = ?
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            
            audit_logger.log_subscription_created(user_id, subscription_id, plan_id, plan['amount'])
            
            return {'success': True, 'message': 'Subscription created'}
            
        except Exception as e:
            logger.error(f"Checkout completion handling error: {e}")
            return {'success': False, 'error': 'Failed to process checkout'}
    
    def _handle_payment_succeeded(self, invoice_data: Dict) -> Dict[str, Any]:
        """Handle successful payment"""
        
        try:
            subscription_id = invoice_data.get('subscription')
            customer_id = invoice_data.get('customer')
            amount_paid = invoice_data.get('amount_paid')
            
            # Update subscription record
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE user_subscriptions 
                SET status = 'active', 
                    current_period_start = ?,
                    current_period_end = ?,
                    updated_at = ?
                WHERE stripe_subscription_id = ?
            ''', (
                datetime.fromtimestamp(invoice_data['period_start']).isoformat(),
                datetime.fromtimestamp(invoice_data['period_end']).isoformat(),
                datetime.now().isoformat(),
                subscription_id
            ))
            
            # Get user_id for logging
            cursor.execute('''
                SELECT user_id FROM user_subscriptions 
                WHERE stripe_subscription_id = ?
            ''', (subscription_id,))
            
            result = cursor.fetchone()
            if result:
                user_id = result[0]
                audit_logger.log_payment_succeeded(user_id, subscription_id, amount_paid)
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'message': 'Payment processed'}
            
        except Exception as e:
            logger.error(f"Payment success handling error: {e}")
            return {'success': False, 'error': 'Failed to process payment'}
    
    def _handle_payment_failed(self, invoice_data: Dict) -> Dict[str, Any]:
        """Handle failed payment"""
        
        try:
            subscription_id = invoice_data.get('subscription')
            
            # Update subscription status
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE user_subscriptions 
                SET status = 'past_due', updated_at = ?
                WHERE stripe_subscription_id = ?
            ''', (datetime.now().isoformat(), subscription_id))
            
            # Get user_id for logging
            cursor.execute('''
                SELECT user_id FROM user_subscriptions 
                WHERE stripe_subscription_id = ?
            ''', (subscription_id,))
            
            result = cursor.fetchone()
            if result:
                user_id = result[0]
                audit_logger.log_payment_failed(user_id, subscription_id)
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'message': 'Payment failure recorded'}
            
        except Exception as e:
            logger.error(f"Payment failure handling error: {e}")
            return {'success': False, 'error': 'Failed to process payment failure'}
    
    def _handle_subscription_cancelled(self, subscription_data: Dict) -> Dict[str, Any]:
        """Handle subscription cancellation"""
        
        try:
            subscription_id = subscription_data.get('id')
            
            # Update subscription status
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE user_subscriptions 
                SET status = 'cancelled', updated_at = ?
                WHERE stripe_subscription_id = ?
            ''', (datetime.now().isoformat(), subscription_id))
            
            # Get user_id for logging and role update
            cursor.execute('''
                SELECT user_id FROM user_subscriptions 
                WHERE stripe_subscription_id = ?
            ''', (subscription_id,))
            
            result = cursor.fetchone()
            if result:
                user_id = result[0]
                
                # Update user role back to regular user
                cursor.execute('''
                    UPDATE users SET role = 'user' WHERE user_id = ?
                ''', (user_id,))
                
                audit_logger.log_subscription_cancelled(user_id, subscription_id)
            
            conn.commit()
            conn.close()
            
            return {'success': True, 'message': 'Subscription cancelled'}
            
        except Exception as e:
            logger.error(f"Subscription cancellation handling error: {e}")
            return {'success': False, 'error': 'Failed to process cancellation'}
    
    def get_user_subscription(self, user_id: int) -> Dict[str, Any]:
        """Get user's subscription information"""
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM user_subscriptions 
                WHERE user_id = ? 
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id,))
            
            subscription = cursor.fetchone()
            conn.close()
            
            if not subscription:
                return {'success': True, 'subscription': None}
            
            plan_id = subscription[2]
            plan = self.plans.get(plan_id, {})
            
            return {
                'success': True,
                'subscription': {
                    'subscription_id': subscription[1],
                    'plan_id': plan_id,
                    'plan_name': plan.get('name', 'Unknown'),
                    'status': subscription[5],
                    'amount': subscription[6],
                    'currency': subscription[7],
                    'interval': subscription[8],
                    'current_period_start': subscription[9],
                    'current_period_end': subscription[10],
                    'features': plan.get('features', []),
                    'created_at': subscription[11],
                    'updated_at': subscription[12]
                }
            }
            
        except Exception as e:
            logger.error(f"Get user subscription error: {e}")
            return {'success': False, 'error': 'Failed to get subscription'}
    
    def get_available_plans(self) -> Dict[str, Any]:
        """Get available subscription plans"""
        
        return {
            'success': True,
            'plans': self.plans
        }
    
    def cancel_subscription(self, user_id: int, at_period_end: bool = True) -> Dict[str, Any]:
        """Cancel user's subscription"""
        
        try:
            # Get subscription info
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT stripe_subscription_id FROM user_subscriptions 
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            
            result = cursor.fetchone()
            if not result:
                return {'success': False, 'error': 'No active subscription found'}
            
            subscription_id = result[0]
            
            # Cancel in Stripe
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=at_period_end
            )
            
            # Update database
            status = 'cancelled' if not at_period_end else 'active'
            cursor.execute('''
                UPDATE user_subscriptions 
                SET status = ?, updated_at = ?
                WHERE user_id = ?
            ''', (status, datetime.now().isoformat(), user_id))
            
            conn.commit()
            conn.close()
            
            audit_logger.log_subscription_cancelled(user_id, subscription_id)
            
            return {
                'success': True,
                'message': 'Subscription cancelled successfully'
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription cancellation error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Subscription cancellation error: {e}")
            return {'success': False, 'error': 'Failed to cancel subscription'}
    
    def update_subscription_plan(self, user_id: int, new_plan_id: str) -> Dict[str, Any]:
        """Update user's subscription plan"""
        
        try:
            if new_plan_id not in self.plans:
                return {'success': False, 'error': 'Invalid plan'}
            
            # Get current subscription
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT stripe_subscription_id FROM user_subscriptions 
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            
            result = cursor.fetchone()
            if not result:
                return {'success': False, 'error': 'No active subscription found'}
            
            subscription_id = result[0]
            new_plan = self.plans[new_plan_id]
            
            # Update in Stripe
            stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': stripe.Subscription.retrieve(subscription_id)['items']['data'][0].id,
                    'price': new_plan['price_id']
                }]
            )
            
            # Update database
            cursor.execute('''
                UPDATE user_subscriptions 
                SET plan_id = ?, amount = ?, currency = ?, 
                    interval = ?, updated_at = ?
                WHERE user_id = ?
            ''', (
                new_plan_id,
                new_plan['amount'],
                new_plan['currency'],
                new_plan['interval'],
                datetime.now().isoformat(),
                user_id
            ))
            
            conn.commit()
            conn.close()
            
            audit_logger.log_subscription_updated(user_id, subscription_id, new_plan_id)
            
            return {
                'success': True,
                'message': 'Subscription updated successfully'
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription update error: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Subscription update error: {e}")
            return {'success': False, 'error': 'Failed to update subscription'}


# Global instance
payment_manager = PaymentManager()
