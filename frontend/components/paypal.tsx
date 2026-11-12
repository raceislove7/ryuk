"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import type { Checkout } from "../lib/contracts";

interface Buttons {
  render: (element: HTMLElement) => Promise<void>;
  close: () => Promise<void>;
}
interface PayPal {
  Buttons: (options: {
    style: Record<string, unknown>;
    createOrder: () => Promise<string>;
    onApprove: () => Promise<void>;
    onCancel: () => Promise<void>;
    onError: () => void;
  }) => Buttons;
}
declare global {
  interface Window {
    paypal?: PayPal;
  }
}
let sdk: Promise<PayPal> | undefined;
let sdkKey = "";
function loadSdk(clientId: string, currency: string): Promise<PayPal> {
  const key = `${clientId}/${currency}`;
  if (sdk && sdkKey === key) return sdk;
  sdkKey = key;
  sdk = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    const query = new URLSearchParams({
      "client-id": clientId,
      currency,
      intent: "capture",
      components: "buttons",
    });
    script.src = `https://www.paypal.com/sdk/js?${query}`;
    const nonce = document.querySelector<HTMLMetaElement>('meta[name="csp-nonce"]')?.content;
    if (!nonce) {
      sdk = undefined;
      reject(new Error("Checkout security policy is unavailable. Reload the page."));
      return;
    }
    script.nonce = nonce;
    script.setAttribute("data-csp-nonce", nonce);
    script.async = true;
    script.onload = () =>
      window.paypal
        ? resolve(window.paypal)
        : reject(new Error("PayPal did not initialize."));
    script.onerror = () => {
      sdk = undefined;
      reject(new Error("PayPal could not be loaded. Please try again."));
    };
    document.head.appendChild(script);
  });
  return sdk;
}
export default function PayPalCheckout({
  proposalId,
  clientId,
  currency,
  inactive = false,
  onRecord,
  onError,
  onActivity,
}: {
  proposalId: string;
  clientId: string;
  currency: string;
  inactive?: boolean;
  onRecord: (checkout: Checkout) => Promise<void>;
  onError: (message: string) => void;
  onActivity: (message: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onRecord, onError, onActivity });
  useEffect(() => {
    callbacks.current = { onRecord, onError, onActivity };
  }, [onRecord, onError, onActivity]);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let canceled = false;
    let buttons: Buttons | undefined;
    let checkout: Checkout | undefined;
    loadSdk(clientId, currency)
      .then(async (paypal) => {
        if (canceled || !host.current) return;
        buttons = paypal.Buttons({
          style: {
            color: "white",
            shape: "rect",
            layout: "vertical",
            label: "paypal",
            height: 44,
          },
          createOrder: async () => {
            callbacks.current.onActivity("Preparing your Sandbox order");
            try {
              checkout = await api<Checkout>("checkouts", "POST", {
                proposal_id: proposalId,
              });
              if (canceled)
                throw new Error(
                  "The case changed before checkout was prepared.",
                );
              await callbacks.current.onRecord(checkout);
            } finally {
              callbacks.current.onActivity("");
            }
            if (
              !checkout.paypal_order_id ||
              checkout.order_creation !== "READY" ||
              checkout.state !== "AWAITING_PAYPAL_BUYER"
            )
              throw new Error(
                "The backend could not prepare checkout. Review the recorded state.",
              );
            return checkout.paypal_order_id;
          },
          onApprove: async () => {
            if (!checkout) return;
            // Callback is only a request to the backend, never evidence of payment.
            callbacks.current.onActivity(
              "Waiting for backend capture confirmation",
            );
            try {
              const result = await api<Checkout>(
                `checkouts/${checkout.checkout_id}/capture`,
                "POST",
                {},
              );
              await callbacks.current.onRecord(result);
            } finally {
              callbacks.current.onActivity("");
            }
          },
          onCancel: async () => {
            callbacks.current.onActivity("Recording buyer cancellation");
            try {
              if (checkout)
                await callbacks.current.onRecord(
                  await api<Checkout>(
                    `checkouts/${checkout.checkout_id}/cancel`,
                    "POST",
                    {},
                  ),
                );
            } finally {
              callbacks.current.onActivity("");
            }
          },
          onError: () =>
            callbacks.current.onError(
              "PayPal could not complete this action. Check the backend status before trying anything else.",
            ),
        });
        await buttons.render(host.current);
        if (!canceled) setReady(true);
      })
      .catch((error) => {
        if (!canceled)
          callbacks.current.onError(
            error instanceof Error ? error.message : "PayPal is unavailable.",
          );
      });
    return () => {
      canceled = true;
      void buttons?.close().catch(() => {});
    };
  }, [proposalId, clientId, currency]);
  return (
    <div className="paypal-slot">
      {/* Keep SDK nodes alive until its callback resolves. Closing/unmounting here
          on a terminal/pending backend response can strand the PayPal popup. */}
      <div ref={host} style={{ display: inactive ? "none" : undefined }} />
      {!inactive && !ready && <p className="subtle">Connecting to PayPal Sandbox…</p>}
      {inactive && <p className="subtle">Continue with the backend payment record below.</p>}
    </div>
  );
}
