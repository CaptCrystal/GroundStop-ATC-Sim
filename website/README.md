# GroundStop Website

Next.js 14 marketing site with Stripe payment integration.

## Quick Start

```bash
cd website
npm install
cp .env.local.example .env.local   # then fill in your Stripe key
npm run dev
```

Open http://localhost:3000

## Stripe Setup (2 minutes)

1. Go to https://dashboard.stripe.com/apikeys
2. Copy your **Secret key** (`sk_live_...` or `sk_test_...` for testing)
3. Paste it into `.env.local` as `STRIPE_SECRET_KEY`
4. Set `NEXT_PUBLIC_SITE_URL` to your production domain (e.g. `https://groundstop.gg`)

The API route at `/api/checkout` creates a $15 Stripe Checkout session automatically — no price ID needed.

## Deploy to Vercel

```bash
npx vercel
```

Set the same env vars in the Vercel dashboard under Settings → Environment Variables.

## File Structure

```
app/
  layout.tsx              Root layout + metadata
  page.tsx                Main landing page
  globals.css             Global styles + Tailwind
  checkout-success/
    page.tsx              Post-purchase thank-you page
  api/checkout/
    route.ts              Stripe Checkout session API

components/
  Navbar.tsx              Sticky nav with mobile menu
  AtcTerminal.tsx         Animated ATC typewriter demo
  BuyButton.tsx           Stripe checkout trigger
  ScrollReveal.tsx        Intersection observer reveal wrapper
```
