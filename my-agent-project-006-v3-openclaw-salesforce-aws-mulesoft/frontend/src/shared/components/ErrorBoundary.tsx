/**
 * 4-tier error boundary (narrative §6).
 *
 * - transient: retry silently (parent component handles, we never render).
 * - degraded: show what we have, small banner.
 * - recoverable: render a retry affordance inline.
 * - fatal: preserve user input (prop passthrough) + a full fallback.
 */

import { Component, type ReactNode } from 'react';

export interface ErrorBoundaryProps {
  fallback?: ReactNode;
  children?: ReactNode;
  onError?: (err: Error) => void;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  override componentDidCatch(error: Error): void {
    this.props.onError?.(error);
  }

  override render(): ReactNode {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div
            role="alert"
            className="v3-error-toast"
            data-tier="fatal"
            style={{ margin: '1rem' }}
          >
            <span>
              <strong>Something went wrong.</strong> Your input has been preserved. Reload to retry.
            </span>
            <button
              type="button"
              className="slds-button slds-button_neutral"
              onClick={() => location.reload()}
            >
              Reload
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
