import { useEffect } from "react";

declare global {
  namespace JSX {
    interface IntrinsicElements {
      "stripe-buy-button": {
        "buy-button-id": string;
        "publishable-key": string;
      };
    }
  }
}

export default function BuyButton() {
  useEffect(() => {
    if (document.querySelector('script[src="https://js.stripe.com/v3/buy-button.js"]')) return;
    const script = document.createElement("script");
    script.src = "https://js.stripe.com/v3/buy-button.js";
    script.async = true;
    document.head.appendChild(script);
  }, []);

  return (
    <stripe-buy-button
      buy-button-id="buy_btn_1TBm2LPWpiJ1w4PQvmwNCGhi"
      publishable-key="pk_live_51StHx0PWpiJ1w4PQxGl3fDCm5AE1gkhxV7XRZXuenlhe3AT51JSZ8fIXrZtajeiWZ30Zws7AasvkU7JeIU6NPDvr006tyfatiB"
    />
  );
}
