import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StreamingText } from '../../../src/shared/components/StreamingText';

describe('StreamingText', () => {
  it('stitches citation chips inline with text', () => {
    render(
      <StreamingText
        markdown="NVDA datacenter grew 143%[src:s1]. Gaming rose 11%[src:s2]."
        citations={{
          s1: {
            span_id: 's1',
            source_id: 'src-1',
            source_type: 'filing',
            label: '10-K Item 7',
          },
          s2: {
            span_id: 's2',
            source_id: 'src-2',
            source_type: 'filing',
            label: '10-K Item 7',
          },
        }}
      />,
    );
    expect(screen.getByTestId('chip-s1')).toHaveAttribute('data-pending', 'false');
    expect(screen.getByTestId('chip-s2')).toHaveAttribute('data-pending', 'false');
  });

  it('renders pending chips when citation channel lags', () => {
    render(<StreamingText markdown="Sentence one[src:late]." citations={{}} isStreaming />);
    expect(screen.getByTestId('chip-late')).toHaveAttribute('data-pending', 'true');
  });
});
