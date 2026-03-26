import React from 'react';
import { Check } from 'lucide-react';
import { StepId } from './types';

const STEPS = [
  { id: 1, title: 'Cliente & Programa' },
  { id: 2, title: 'Voo de Ida' },
  { id: 3, title: 'Voo de Volta' },
  { id: 4, title: 'Passageiros' },
  { id: 5, title: 'Valores' },
  { id: 6, title: 'Revisão' },
] as const;

interface Props {
  currentStep: StepId;
  onStepClick: (id: StepId) => void;
}

export const WizardStepper: React.FC<Props> = ({ currentStep, onStepClick }) => {
  return (
    <div className='grid grid-cols-6 gap-4'>
      {STEPS.map((step) => {
        const complete = step.id < currentStep;
        const active = step.id === currentStep;
        const blocked = step.id > currentStep;

        return (
          <button
            key={step.id}
            type='button'
            disabled={blocked}
            onClick={() => onStepClick(step.id as StepId)}
            className='flex flex-col items-center gap-2 transition-all duration-200 disabled:cursor-not-allowed'
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-200 ${
                complete
                  ? 'bg-green-500 text-white'
                  : active
                    ? 'bg-blue-600 text-white ring-2 ring-blue-500'
                    : 'bg-gray-300 text-gray-500'
              }`}
            >
              {complete ? <Check size={14} /> : step.id}
            </div>
            <span className={`text-xs ${active || complete ? 'text-gray-900' : 'text-gray-500'}`}>{step.title}</span>
          </button>
        );
      })}
    </div>
  );
};
