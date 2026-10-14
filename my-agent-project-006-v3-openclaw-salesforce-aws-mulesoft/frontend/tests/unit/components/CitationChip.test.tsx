import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CitationChip } from '../../../src/shared/components/CitationChip';

describe('CitationChip', () => {
  it('renders pending state when no citation metadata yet', () => {
    render(<CitationChip spanId="s1" citation={undefined} />);
    const chip = screen.getByTestId('chip-s1');
    expect(chip).toHaveAttribute('data-pending', 'true');
    expect(chip).toHaveTextContent('citation…');
  });

  it('renders label and opens source on click', () => {
    const onOpen = vi.fn();
    render(
      <CitationChip
        spanId="s2"
        citation={{
          span_id: 's2',
          source_id: 'src-1',
          source_type: 'filing',
          label: '10-K Item 1A',
          page: 12,
        }}
        onOpen={onOpen}
      />,
    );
    const chip = screen.getByTestId('chip-s2');
    expect(chip).toHaveTextContent('10-K Item 1A');
    fireEvent.click(chip);
    expect(onOpen).toHaveBeenCalledWith('src-1');
  });
});
