/**
 * WIZARD MANAGER - Gerencimento de estado e navegação do wizard
 * Integração total com Django forms e localStorage
 */

class WizardManager {
  constructor() {
    this.currentStep = 1;
    this.maxSteps = 6;
    this.wizardData = this.loadFromLocalStorage() || {};
    this.form = document.querySelector('.form-shell');
    this.init();
  }

  init() {
    this.attachEventListeners();
    this.loadFormValues();
    this.displayStep(this.currentStep);
    this.setupAutoSave();
    this.syncSelectDisplays();
  }

  /**
   * NAVEGAÇÃO ENTRE PASSOS
   */
  attachEventListeners() {
    // Cliques no stepper
    document.querySelectorAll('.wizard-stepper__item').forEach((btn, idx) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const step = parseInt(btn.dataset.goStep);
        if (this.canNavigateToStep(step)) {
          this.goToStep(step);
        }
      });
    });

    // Botões de navegação (próximo/anterior/finalizar)
    document.addEventListener('click', (e) => {
      if (e.target.closest('[data-wizard-prev]')) {
        e.preventDefault();
        this.previousStep();
      }
      if (e.target.closest('[data-wizard-next]')) {
        e.preventDefault();
        if (this.validateCurrentStep()) {
          this.nextStep();
        }
      }
      if (e.target.closest('[data-wizard-finish]')) {
        e.preventDefault();
        if (this.validateAllSteps()) {
          this.finishEmission();
        } else {
          this.showError('Preencha todos os campos obrigatórios antes de finalizar.');
        }
      }
    });

    // Sincronizar dados ao mudar campos
    this.form.querySelectorAll('input, select, textarea').forEach((field) => {
      field.addEventListener('change', () => {
        this.syncSelectDisplays();
        this.saveToLocalStorage();
      });
    });
  }

  /**
   * EXIBIÇÃO DE PASSOS
   */
  displayStep(step) {
    // Esconder todos os passos
    document.querySelectorAll('.wizard-step').forEach((s) => {
      s.classList.remove('is-active');
    });

    // Mostrar apenas o step atual
    document.querySelectorAll(`[data-step="${step}"]`).forEach((s) => {
      s.classList.add('is-active');
    });

    // Atualizar stepper
    this.updateStepper(step);
    
    // Atualizar botões de navegação
    this.updateNavButtons(step);

    // Scroll para o topo
    document.querySelector('.form-wrapper')?.scrollIntoView({ behavior: 'smooth' });
  }

  updateStepper(step) {
    document.querySelectorAll('.wizard-stepper__item').forEach((btn, idx) => {
      const btnStep = parseInt(btn.dataset.goStep);
      btn.classList.remove('is-active', 'is-complete');

      if (btnStep === step) {
        btn.classList.add('is-active');
      } else if (btnStep < step) {
        btn.classList.add('is-complete');
      }
    });
  }

  updateNavButtons(step) {
    const prevBtn = document.querySelector('[data-wizard-prev]');
    const nextBtn = document.querySelector('[data-wizard-next]');
    const finishBtn = document.querySelector('[data-wizard-finish]');

    // Step 1: Sem botão voltar
    if (prevBtn) {
      prevBtn.style.display = step === 1 ? 'none' : 'inline-flex';
    }

    // Steps 1-5: Mostrar próximo
    if (nextBtn) {
      nextBtn.style.display = step < 6 ? 'inline-flex' : 'none';
    }

    // Step 6: Mostrar finalizar
    if (finishBtn) {
      finishBtn.style.display = step === 6 ? 'inline-flex' : 'none';
    }
  }

  goToStep(step) {
    if (step >= 1 && step <= this.maxSteps) {
      this.currentStep = step;
      this.displayStep(step);
      this.syncSelectDisplays();
      this.saveToLocalStorage();
    }
  }

  nextStep() {
    if (this.currentStep < this.maxSteps) {
      this.goToStep(this.currentStep + 1);
    }
  }

  previousStep() {
    if (this.currentStep > 1) {
      this.goToStep(this.currentStep - 1);
    }
  }

  canNavigateToStep(step) {
    // Só permite voltar, não pular
    return step <= this.currentStep || step === this.currentStep + 1;
  }

  /**
   * VALIDAÇÕES
   */
  validateCurrentStep() {
    const stepValidations = {
      1: () => this.validateStep1(),
      2: () => this.validateStep2(),
      3: () => this.validateStep3(),
      4: () => this.validateStep4(),
      5: () => this.validateStep5(),
      6: () => true,
    };

    const validator = stepValidations[this.currentStep];
    return validator ? validator() : true;
  }

  validateStep1() {
    // Cliente & Programa
    const tipoEmissao = document.querySelector('[name="tipo_emissao"]');
    const cliente = document.querySelector('[name="cliente"]');
    const contaAdm = document.querySelector('[name="conta_administrada"]');
    const programa = document.querySelector('[name="programa"]');

    if (!tipoEmissao?.value) {
      this.showError('Selecione o tipo de emissão');
      return false;
    }

    if (tipoEmissao.value === 'cliente' && !cliente?.value) {
      this.showError('Selecione o cliente');
      return false;
    }

    if (tipoEmissao.value === 'administrada' && !contaAdm?.value) {
      this.showError('Selecione a conta administrada');
      return false;
    }

    if (!programa?.value) {
      this.showError('Selecione o programa');
      return false;
    }

    return true;
  }

  validateStep2() {
    // Voo de Ida
    const origem = document.querySelector('[name="aeroporto_partida"]');
    const destino = document.querySelector('[name="aeroporto_destino"]');
    const companhia = document.querySelector('[name="companhia_aerea"]');
    const data = document.querySelector('[name="data_ida"]');

    if (!origem?.value) {
      this.showError('Informe o aeroporto de partida');
      return false;
    }

    if (!destino?.value) {
      this.showError('Informe o aeroporto de destino');
      return false;
    }

    if (!companhia?.value) {
      this.showError('Selecione a companhia aérea');
      return false;
    }

    if (!data?.value) {
      this.showError('Informe a data e horário da ida');
      return false;
    }

    return true;
  }

  validateStep3() {
    // Voo de Volta (opcional)
    return true;
  }

  validateStep4() {
    // Passageiros
    const adultos = parseInt(document.querySelector('[name="qtd_adultos"]')?.value || 0);
    const criancas = parseInt(document.querySelector('[name="qtd_criancas"]')?.value || 0);
    const bebes = parseInt(document.querySelector('[name="qtd_bebes"]')?.value || 0);
    const total = adultos + criancas + bebes;

    if (total === 0) {
      this.showError('Adicione pelo menos um passageiro');
      return false;
    }

    // Validar que todos os passageiros têm nome e CPF
    const passageiroInputs = document.querySelectorAll('[name$="-nome"]');
    for (let input of passageiroInputs) {
      if (!input.value?.trim()) {
        this.showError('Preencha o nome de todos os passageiros');
        return false;
      }
    }

    const cpfInputs = document.querySelectorAll('[name$="-cpf"]');
    for (let input of cpfInputs) {
      if (!input.value?.trim()) {
        this.showError('Preencha o CPF de todos os passageiros');
        return false;
      }
    }

    return true;
  }

  validateStep5() {
    // Valores
    const localizador = document.querySelector('[name="localizador"]');
    const valorRef = document.querySelector('[name="valor_referencia"]');

    if (!localizador?.value?.trim()) {
      this.showError('Informe o localizador');
      return false;
    }

    if (!valorRef?.value) {
      this.showError('Informe o valor de referência');
      return false;
    }

    return true;
  }

  validateAllSteps() {
    for (let step = 1; step <= 5; step++) {
      const stepValidations = {
        1: () => this.validateStep1(),
        2: () => this.validateStep2(),
        3: () => this.validateStep3(),
        4: () => this.validateStep4(),
        5: () => this.validateStep5(),
      };

      const validator = stepValidations[step];
      if (validator && !validator()) {
        return false;
      }
    }
    return true;
  }

  /**
   * SINCRONIZAÇÃO DE VALORES
   */
  loadFormValues() {
    // Carregar valores dos campos Django no localStorage
    this.form.querySelectorAll('input, select, textarea').forEach((field) => {
      if (field.value) {
        this.wizardData[field.name] = field.value;
      }
    });
  }

  syncSelectDisplays() {
    // Sincronizar displays de campos select com seus valores

    // TIPO EMISSÃO
    const tipoEmissao = document.querySelector('[name="tipo_emissao"]');
    if (tipoEmissao) {
      this.handleTipoEmissaoChange(tipoEmissao.value);
    }

    // PROGRAMA
    const programa = document.querySelector('[name="programa"]');
    if (programa && programa.value) {
      this.updateProgramaInfo(programa.value);
    }

    // ESCALAS
    const temEscalaIda = document.querySelector('#ida-tem-escala');
    const temEscalaVolta = document.querySelector('#volta-tem-escala');
    if (temEscalaIda) {
      this.toggleEscalas('ida', temEscalaIda.checked);
    }
    if (temEscalaVolta) {
      this.toggleEscalas('volta', temEscalaVolta.checked);
    }

    // VOLTA
    const possuiVolta = document.querySelector('#possui-volta');
    if (possuiVolta) {
      this.toggleVolta(possuiVolta.checked);
    }
  }

  handleTipoEmissaoChange(tipo) {
    const clienteWrapper = document.querySelector('#cliente-wrapper');
    const contaAdmWrapper = document.querySelector('#conta-adm-wrapper');
    const emissorWrapper = document.querySelector('#emissor-parceiro-wrapper');

    // Esconder todos
    clienteWrapper?.classList.add('hidden');
    contaAdmWrapper?.classList.add('hidden');
    emissorWrapper?.classList.add('hidden');

    // Mostrar conforme o tipo
    if (tipo === '1' || tipo === 'cliente') {
      clienteWrapper?.classList.remove('hidden');
    } else if (tipo === '2' || tipo === 'administrada') {
      contaAdmWrapper?.classList.remove('hidden');
    } else if (tipo === '3' || tipo === 'parceiro') {
      emissorWrapper?.classList.remove('hidden');
    }
  }

  updateProgramaInfo(programaId) {
    // Buscar info do programa e atualizar badges
    const badgeMap = {
      '1': { name: 'LATAM', class: 'latam', color: '#EF4444' },
      '2': { name: 'Smiles', class: 'smiles', color: '#F97316' },
      '3': { name: 'Azul', class: 'azul', color: '#3B82F6' },
      '4': { name: 'Privilege', class: 'privilege', color: '#A855F7' },
    };

    const badge = badgeMap[programaId];
    if (badge) {
      const statusBadge = document.querySelector('#cpf-status-badge');
      if (statusBadge) {
        statusBadge.innerHTML = `<span class="program-badge ${badge.class}">${badge.name}</span>`;
      }
    }
  }

  toggleEscalas(tipo, isChecked) {
    const wrapper = document.querySelector(`#escala-${tipo}-wrapper`);
    if (wrapper) {
      if (isChecked) {
        wrapper.classList.remove('hidden');
      } else {
        wrapper.classList.add('hidden');
      }
    }
  }

  toggleVolta(isChecked) {
    const voltaCard = document.querySelector('#voo-volta-card');
    if (voltaCard) {
      voltaCard.classList.toggle('hidden', !isChecked);
    }
  }

  /**
   * AUTOSAVE
   */
  setupAutoSave() {
    const autoSaveDelay = 2000; // 2 segundos
    let saveTimeout;

    this.form.querySelectorAll('input, select, textarea').forEach((field) => {
      field.addEventListener('change', () => {
        clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
          this.saveToLocalStorage();
          this.showAutoSaveIndicator();
        }, autoSaveDelay);
      });
    });
  }

  saveToLocalStorage() {
    this.form.querySelectorAll('input, select, textarea').forEach((field) => {
      if (field.type !== 'hidden' && field.type !== 'submit') {
        if (field.type === 'checkbox') {
          this.wizardData[field.name] = field.checked;
        } else {
          this.wizardData[field.name] = field.value;
        }
      }
    });

    this.wizardData.__step = this.currentStep;
    localStorage.setItem('emission_wizard_draft', JSON.stringify(this.wizardData));
  }

  loadFromLocalStorage() {
    const saved = localStorage.getItem('emission_wizard_draft');
    return saved ? JSON.parse(saved) : null;
  }

  showAutoSaveIndicator() {
    const indicator = document.querySelector('#wizard-autosave');
    if (indicator) {
      indicator.textContent = '✓ Rascunho salvo';
      indicator.style.color = '#10B981';

      setTimeout(() => {
        indicator.textContent = 'Rascunho local ativo';
        indicator.style.color = 'inherit';
      }, 3000);
    }
  }

  /**
   * FINALIZAR EMISSÃO
   */
  finishEmission() {
    const button = document.querySelector('[data-wizard-finish]');
    if (button) {
      button.disabled = true;
      button.innerHTML = '<span class="spinner"></span> Salvando emissão...';

      // Enviar o formulário
      setTimeout(() => {
        localStorage.removeItem('emission_wizard_draft');
        this.form.submit();
      }, 500);
    }
  }

  showError(message) {
    const alert = document.createElement('div');
    alert.className = 'alert-error';
    alert.innerHTML = `<p>❌ ${message}</p>`;
    alert.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      background: #EF4444;
      color: white;
      padding: 1rem 1.5rem;
      border-radius: 6px;
      z-index: 1000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    document.body.appendChild(alert);

    setTimeout(() => alert.remove(), 5000);
  }
}

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', () => {
  window.wizardManager = new WizardManager();
});
