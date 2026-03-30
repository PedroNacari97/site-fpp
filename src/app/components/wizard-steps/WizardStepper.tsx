import React from 'react';
import { Check } from 'lucide-react';
import { cn, WIZARD_STEPS } from './theme';
import { StepId } from './types';

interface Props {
  currentStep: StepId;
  onStepClick: (id: StepId) => void;
}

export const WizardStepper: React.FC<Props> = ({ currentStep, onStepClick }) => {
  return (
    <div className='grid grid-cols-2 gap-5 md:grid-cols-3 xl:grid-cols-6 xl:gap-0'>
      {WIZARD_STEPS.map((step, index) => {
        const complete = step.id < currentStep;
        const active = step.id === currentStep;
        const blocked = step.id > currentStep;

        return (
          <button
            key={step.id}
            type='button'
            disabled={blocked}
            onClick={() => onStepClick(step.id)}
            className='group relative flex flex-col items-center gap-2 text-center disabled:cursor-not-allowed'
          >
            {index < WIZARD_STEPS.length - 1 && (
              <span
                className={cn(
                  'absolute left-[calc(50%+42px)] top-6 hidden h-[2px] w-[calc(100%-84px)] rounded-full xl:block',
                  complete ? 'bg-[#00c950]' : 'bg-[#364153]',
                )}
              />
            )}

            <span
              className={cn(
                'flex h-12 w-12 items-center justify-center rounded-full text-sm font-semibold transition',
                complete && 'bg-[#00c950] text-white',
                active && 'bg-[#155dfc] text-white shadow-[0_0_0_6px_rgba(21,93,252,0.16)]',
                blocked && 'bg-[#364153] text-[#99a1af]',
              )}
            >
              {complete ? <Check size={18} /> : step.id}
            </span>

            <div className='max-w-[112px] space-y-1'>
              <p className={cn('text-sm font-medium', active || complete ? 'text-white' : 'text-[#99a1af]')}>{step.title}</p>
              <p className='text-xs leading-4 text-[#6a7282]'>{step.subtitle}</p>
            </div>
          </button>
        );
      })}
    </div>
  );
};
