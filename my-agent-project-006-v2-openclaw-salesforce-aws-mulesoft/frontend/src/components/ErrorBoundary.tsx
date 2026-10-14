/**
 * Error Boundary — catches React render errors in children.
 * Shows a recovery UI with retry button.
 */

import { Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="slds-p-around_large slds-text-align_center" role="alert" style={{ marginTop: '4rem' }}>
          <p className="slds-text-heading_medium slds-m-bottom_small">Something went wrong</p>
          <p className="slds-text-body_regular slds-text-color_weak slds-m-bottom_medium">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button className="slds-button slds-button_brand" onClick={this.handleRetry}>
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
