import posthog from "posthog-js";

type Event =
  | { name: "popup_opened" }
  | { name: "token_checked"; mint: string }
  | { name: "address_checked"; address: string }
  | { name: "report_submitted" };

let started = false;

function start(): boolean {
  if (started) return true;
  if (!POSTHOG_KEY) return false;
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    persistence: "localStorage",
    person_profiles: "always",
    disable_external_dependency_loading: true,
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    rageclick: false,
    capture_heatmaps: false,
    capture_dead_clicks: false,
    capture_performance: false,
    capture_exceptions: false,
    disable_session_recording: true,
    disable_surveys: true,
    disable_web_experiments: true,
    advanced_disable_flags: true,
  });
  started = true;
  return true;
}

export function track(event: Event): void {
  if (!start()) return;
  const { name, ...properties } = event;
  posthog.capture(name, properties);
}
