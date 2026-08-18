class ProjectPlanner {
    constructor() {
        this.token = localStorage.getItem('token');
        this.currentUser = localStorage.getItem('currentUser');
        this.currentProject = null;
        this.currentTask = null;
        this.tasks = [];
        this.resources = [];
        this.planData = null;
        this.pollingInterval = null;
        this.BASE_URL = 'http://localhost:8000';
        this.isEditingResource = false;
        this.editingResourceId = null;
        
        this.init();
    }

    init() {
        console.log('Init called');
        
        this.bindEvents();
        
        if (this.token) {
            // Восстановить план из localStorage
            const savedPlanData = localStorage.getItem('lastPlanData');
            const savedProjectId = localStorage.getItem('lastProjectId');
            const savedTasks = localStorage.getItem('lastTasks');
            
            if (savedPlanData && savedProjectId) {
                try {
                    this.planData = JSON.parse(savedPlanData);
                    this.tasks = JSON.parse(savedTasks || '[]');
                } catch (e) {
                    console.error('Error restoring plan from localStorage:', e);
                    this.planData = null;
                }
            }
            
            // НЕ вызывать showMainScreen() здесь — loadProjects() сам покажет экран
            this.loadProjects();
        } else {
            this.showAuthScreen();
        }
        
        console.log('Init completed');
    }

    exportPlan() {
        if (!this.currentProject) {
            this.showNotification('Выберите проект', 'error');
            return;
        }
        
        const url = `${this.BASE_URL}/api/projects/${this.currentProject.id}/plan/export`;
        window.open(url, '_blank');
    }

    bindEvents() {
        // Аутентификация
        document.querySelectorAll('.auth-tabs .tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchAuthTab(btn.dataset.tab);
            });
        });

        document.getElementById('login-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.login();
        });

        document.getElementById('register-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.register();
        });

        document.getElementById('logout-btn').addEventListener('click', () => this.logout());

        // Проекты
        document.getElementById('create-project-btn').addEventListener('click', () => this.createProject());

        // Вкладки проекта
        document.querySelectorAll('.project-view .tabs .tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.switchProjectTab(btn.dataset.tab);
            });
        });

        const exportBtn = document.getElementById('export-plan-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPlan());
        }
        // Задачи
        document.getElementById('save-task-btn').addEventListener('click', () => this.saveTask());
        document.getElementById('cancel-task-edit').addEventListener('click', () => this.cancelTaskEdit());

        // Ресурсы
        document.getElementById('save-resource-btn').addEventListener('click', () => this.saveResource());
        
        // Добавляем обработчик для кнопки отмены редактирования ресурса
        document.getElementById('cancel-resource-edit').addEventListener('click', () => this.cancelResourceEdit());

        // План
        document.getElementById('calculate-plan-btn').addEventListener('click', () => this.calculatePlan());
    }

    // API запросы
    async apiRequest(url, method = 'GET', body = null) {
        const fullUrl = url.startsWith('http') ? url : `${this.BASE_URL}${url}`;
        
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token || localStorage.getItem('token')}`
            }
        };
        
        if (body) {
            options.body = JSON.stringify(body);
        }
        
        try {
            console.log(`Making ${method} request to: ${fullUrl}`);
            
            const response = await fetch(fullUrl, options);
            
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                let errorMessage;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}`;
                } catch {
                    errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                }
                throw new Error(errorMessage);
            }
            
            const data = await response.json();
            console.log('Response data:', data);
            return data;
        } catch (error) {
            console.error('API Request Error:', error);
            
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Не удалось подключиться к серверу. Убедитесь, что backend запущен на http://localhost:8000');
            }
            
            throw error;
        }
    }

    // Переключение вкладок аутентификации
    switchAuthTab(tab) {
        console.log('Switching auth tab to:', tab);
        
        document.querySelectorAll('.auth-tabs .tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        document.querySelectorAll('.auth-form').forEach(form => {
            form.classList.toggle('active', form.id === `${tab}-form`);
        });
        
        this.clearAuthMessage();
    }

    // Переключение вкладок проекта
    switchProjectTab(tab) {
        console.log('Switching project tab to:', tab);

        localStorage.setItem('lastTab', tab);

        
        // ✅ ПРИ ПЕРЕКЛЮЧЕНИИ НА ВКЛАДКУ ПЛАНА - ПРОВЕРЯЕМ АКТУАЛЬНОСТЬ
        if (tab === 'plan') {
            // Если план закеширован, но проект изменился - очищаем
            if (this.planData && this.currentProject) {
                // Проверяем, что план принадлежит текущему проекту
                // (зависит от структуры planData)
                if (this.planData.project_id && this.planData.project_id !== this.currentProject.id) {
                    this.planData = null;
                    document.getElementById('gantt-chart').innerHTML = '<p class="no-plan-message">Данные плана устарели. Пересчитайте план.</p>';
                }
            }
        }
        
        // Остальной код
        document.querySelectorAll('.project-view .tabs .tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tab}-tab`);
        });
        
        if (tab === 'tasks') {
            this.loadTaskFormData();
        }
    }

    // Показ экранов
    showAuthScreen() {
        document.getElementById('auth-screen').classList.remove('hidden');
        document.getElementById('main-screen').classList.add('hidden');
    }

    showMainScreen() {
        document.getElementById('auth-screen').classList.add('hidden');
        document.getElementById('main-screen').classList.remove('hidden');
        document.getElementById('current-user').textContent = this.currentUser || 'Пользователь';

        
    }

    // Управление сообщениями
    clearAuthMessage() {
        const messageEl = document.getElementById('auth-message');
        messageEl.textContent = '';
        messageEl.className = 'message';
    }

    showAuthMessage(text, type) {
        const messageEl = document.getElementById('auth-message');
        messageEl.textContent = text;
        messageEl.className = `message ${type}`;
    }

    showNotification(text, type = 'success') {
        // Создаем уведомление
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = text;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            z-index: 9999;
            animation: slideIn 0.3s ease;
            ${type === 'success' ? 'background: #27ae60;' : 'background: #e74c3c;'}
        `;
        
        document.body.appendChild(notification);
        
        // Удаляем через 3 секунды
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    showError(message) {
        console.error('Error:', message);
        this.showNotification(message, 'error');
    }

    // Аутентификация
    
    async login() {
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;

        if (!username || !password) {
            this.showAuthMessage('Введите имя пользователя и пароль', 'error');
            return;
        }

        try {
            console.log('Attempting login...');
            const response = await this.apiRequest('/api/auth/login', 'POST', { username, password });
            console.log('Login successful:', response);
            
            this.token = response.token;
            this.currentUser = username;
            localStorage.setItem('token', this.token);
            localStorage.setItem('currentUser', this.currentUser);
            
            this.showMainScreen();
            
            // Восстановить план из localStorage
            const lastProjectId = localStorage.getItem('lastProjectId');
            
            if (lastProjectId) {
                const savedPlan = localStorage.getItem(`plan_${lastProjectId}`);
                const savedTasks = localStorage.getItem(`tasks_${lastProjectId}`);
                
                if (savedPlan && savedTasks) {
                    try {
                        this.planData = JSON.parse(savedPlan);
                        this.tasks = JSON.parse(savedTasks);
                        console.log('Plan restored from localStorage');
                    } catch (e) {
                        console.error('Error restoring plan:', e);
                        this.planData = null;
                        this.tasks = [];
                    }
                }
            }
            
            this.loadProjects();
        } catch (error) {
            console.error('Login error:', error);
            this.showAuthMessage(error.message, 'error');
        }
    }

    async register() {
        const username = document.getElementById('register-username').value.trim();
        const password = document.getElementById('register-password').value;

        if (!username || !password) {
            this.showAuthMessage('Введите имя пользователя и пароль', 'error');
            return;
        }

        if (password.length < 6) {
            this.showAuthMessage('Пароль должен содержать минимум 6 символов', 'error');
            return;
        }

        try {
            console.log('Attempting registration...');
            const response = await this.apiRequest('/api/auth/register', 'POST', { 
                username, 
                password 
            });
            console.log('Registration successful:', response);
            
            if (response.token) {
                this.token = response.token;
                this.currentUser = username;
                localStorage.setItem('token', this.token);
                localStorage.setItem('currentUser', this.currentUser);
                
                this.showAuthMessage('Регистрация успешна!', 'success');
                
                setTimeout(() => {
                    this.showMainScreen();
                    this.clearPlanCache(); 
                    this.loadProjects();
                }, 1000);
            } else {
                throw new Error('Токен не получен от сервера');
            }
        } catch (error) {
            console.error('Registration error:', error);
            this.showAuthMessage(error.message, 'error');
        }
    }

    logout() {
        // Сохранить план для каждого проекта
        if (this.currentProject && this.planData && this.planData.tasks) {
            localStorage.setItem(`plan_${this.currentProject.id}`, JSON.stringify(this.planData));
            localStorage.setItem(`tasks_${this.currentProject.id}`, JSON.stringify(this.tasks));
            localStorage.setItem('lastProjectId', this.currentProject.id);
        }
        
        // Очищаем состояние
        this.token = null;
        this.currentUser = null;
        this.currentProject = null;
        this.tasks = [];
        this.resources = [];
        this.planData = null;
        this.currentTask = null;
        this.isEditingResource = false;
        this.editingResourceId = null;
        
        this.stopPolling();
        // НЕ вызывать clearPlanCache() — оставить данные в localStorage
        
        localStorage.removeItem('token');
        localStorage.removeItem('currentUser');
        // НЕ удалять plan_*, tasks_*, lastProjectId
        
        this.clearAllUI();
        this.showAuthScreen();
        
        document.getElementById('login-form').reset();
        document.getElementById('register-form').reset();
        this.clearAuthMessage();
    }

    // ДОБАВЬТЕ ЭТОТ МЕТОД:
    clearAllUI() {
        // Очищаем диаграмму Ганта
        const ganttChart = document.getElementById('gantt-chart');
        if (ganttChart) {
            ganttChart.innerHTML = '<p class="no-plan-message">Запустите расчет плана для отображения диаграммы Ганта</p>';
        }
        
        // Очищаем статус плана
        const statusEl = document.getElementById('plan-status');
        const statusText = document.getElementById('plan-status-text');
        if (statusEl && statusText) {
            statusEl.className = 'plan-status';
            statusText.textContent = 'Статус: нет плана';
        }
        
        // Очищаем списки
        document.getElementById('tasks-list').innerHTML = '';
        document.getElementById('resources-list').innerHTML = '';
        document.getElementById('projects-list').innerHTML = '';
        
        // Скрываем проект
        document.getElementById('no-project-selected').classList.remove('hidden');
        document.getElementById('project-view').classList.add('hidden');
    }

    // Проекты
    
    async loadProjects() {
        //this.clearPlanCache();
        
        try {
            const response = await this.apiRequest('/api/projects');
            const projects = response.projects || [];
            this.renderProjects(projects);
            this.showMainScreen();

            
            const lastProjectId = localStorage.getItem('lastProjectId');
            if (lastProjectId) {
                const project = projects.find(p => p.id == lastProjectId);
                if (project) {
                    await this.selectProject(project);
                    
                    // Восстановить вкладку
                    const lastTab = localStorage.getItem('lastTab');
                    if (lastTab) {
                        this.switchProjectTab(lastTab);
                    }
                }
            }
        } catch (error) {
            console.error('Ошибка загрузки проектов:', error);
        }
    }

    renderProjects(projects) {
        const projectsList = document.getElementById('projects-list');
        projectsList.innerHTML = '';
        
        projects.forEach(project => {
            const li = document.createElement('li');
            li.textContent = project.name;
            li.dataset.projectId = project.id;
            li.addEventListener('click', () => this.selectProject(project));
            
            if (this.currentProject && this.currentProject.id === project.id) {
                li.classList.add('active');
            }
            
            projectsList.appendChild(li);
        });
    }

    async createProject() {
        const name = document.getElementById('new-project-name').value.trim();
        
        if (!name) {
            this.showNotification('Введите название проекта', 'error');
            return;
        }

        try {
            const project = await this.apiRequest('/api/projects', 'POST', { name });
            document.getElementById('new-project-name').value = '';
            await this.loadProjects();
            await this.selectProject(project);
            this.showNotification('Проект создан', 'success');
        } catch (error) {
            this.showError(error.message);
        }
    }

    async selectProject(project) {
        localStorage.setItem('lastProjectId', project.id);

        const conflictContainer = document.getElementById('conflict-graph-container');
        if (conflictContainer) {
            conflictContainer.classList.add('hidden');
        }
        
        const ganttChart = document.getElementById('gantt-chart');
        if (ganttChart) {
            ganttChart.classList.remove('hidden');
        }

        if (this.currentProject && this.planData && this.planData.tasks) {
            localStorage.setItem(`plan_${this.currentProject.id}`, JSON.stringify(this.planData));
            localStorage.setItem(`tasks_${this.currentProject.id}`, JSON.stringify(this.tasks));
            localStorage.setItem(`planStatus_${this.currentProject.id}`, 'done');
        }
        
        this.currentProject = null;
        this.currentTask = null;
        this.planData = null;
        this.tasks = [];
        this.resources = [];
        
        this.stopPolling();
        
        document.getElementById('gantt-chart').innerHTML = '<p class="no-plan-message">Запустите расчет плана для отображения диаграммы Ганта</p>';
        document.getElementById('plan-status').className = 'plan-status';
        document.getElementById('plan-status-text').textContent = 'Статус: нет плана';
        
        this.currentProject = project;
        
        document.getElementById('no-project-selected').classList.add('hidden');
        document.getElementById('project-view').classList.remove('hidden');
        document.getElementById('project-name').textContent = project.name;
        
        document.querySelectorAll('.projects-list li').forEach(li => {
            li.classList.toggle('active', li.dataset.projectId == project.id);
        });
        
        await Promise.all([
            this.loadTasks(),
            this.loadResources()
        ]);
        
        // Восстановить состояние для КОНКРЕТНОГО проекта
        const projectPlanStatus = localStorage.getItem(`planStatus_${project.id}`);
        const savedPlan = localStorage.getItem(`plan_${project.id}`);
        const savedTasks = localStorage.getItem(`tasks_${project.id}`);
        
        if (projectPlanStatus === 'error') {
            const gantt = document.getElementById('gantt-chart');
            if (gantt) gantt.classList.add('hidden');
            
            const conflict = document.getElementById('conflict-graph-container');
            if (conflict) conflict.classList.remove('hidden');
            
            this.renderDependencyGraph('conflict-graph');
            this.updatePlanStatus('error');
        } else if (projectPlanStatus === 'done' && savedPlan && savedTasks) {
            const conflict = document.getElementById('conflict-graph-container');
            if (conflict) conflict.classList.add('hidden');
            
            const gantt = document.getElementById('gantt-chart');
            if (gantt) gantt.classList.remove('hidden');
            
            try {
                this.planData = JSON.parse(savedPlan);
                this.tasks = JSON.parse(savedTasks);
                this.renderGanttChart(this.planData, false);
                this.updatePlanStatus('done');
            } catch (e) {
                console.error('Error restoring plan:', e);
            }
        } else {
            const conflict = document.getElementById('conflict-graph-container');
            if (conflict) conflict.classList.add('hidden');
            
            const gantt = document.getElementById('gantt-chart');
            if (gantt) gantt.classList.remove('hidden');
        }
        
        this.loadTaskFormData();
    }
    // Загрузка данных для формы задачи (Баг 1)
    async loadTaskFormData() {
        if (!this.currentProject) return;
        
        try {
            // Загружаем задачи для зависимостей
            const tasksResponse = await this.apiRequest(`/api/projects/${this.currentProject.id}/tasks`);
            this.tasks = tasksResponse.tasks || [];
            
            // Загружаем ресурсы
            const resourcesResponse = await this.apiRequest(`/api/projects/${this.currentProject.id}/resources`);
            this.resources = resourcesResponse.resources || [];
            
            // Отображаем чекбоксы
            this.renderDependencyCheckboxes();
            this.renderResourceCheckboxes();
            
            console.log('Task form data loaded:', {
                tasks: this.tasks.length,
                resources: this.resources.length
            });
        } catch (error) {
            console.error('Error loading task form data:', error);
        }
    }

    // Задачи
    async loadTasks() {
        if (!this.currentProject) return;
        
        try {
            const response = await this.apiRequest(`/api/projects/${this.currentProject.id}/tasks`);
            this.tasks = response.tasks || [];
            this.renderTasks();
            this.renderDependencyCheckboxes();
            this.renderResourceCheckboxes();
            //this.renderDependencyGraph('tasks-graph');
        } catch (error) {
            console.error('Ошибка загрузки задач:', error);
        }
    }

    renderTasks() {
        const tasksList = document.getElementById('tasks-list');
        tasksList.innerHTML = '';
        
        if (this.tasks.length === 0) {
            tasksList.innerHTML = '<tr><td colspan="6" style="text-align: center;">Нет задач. Создайте первую задачу.</td></tr>';
            return;
        }
        
        this.tasks.forEach(task => {
            const tr = document.createElement('tr');
            
            const depsText = (task.dependencies || []).map(depId => {
                const depTask = this.tasks.find(t => t.id === depId);
                return depTask ? depTask.name : depId;
            }).join(', ');
            
            const resourcesText = (task.resource_ids || []).map(resId => {
                const resource = this.resources.find(r => r.id === resId);
                return resource ? resource.name : resId;
            }).join(', ');
            
            tr.innerHTML = `
                <td>${task.id}</td>
                <td>${task.name}</td>
                <td>${task.duration}</td>
                <td>${depsText || '-'}</td>
                <td>${resourcesText || '-'}</td>
                <td>
                    <button class="action-btn edit-btn" onclick="app.editTask(${task.id})">Редактировать</button>
                    <button class="action-btn delete-btn" onclick="app.deleteTask(${task.id})">Удалить</button>
                </td>
            `;
            
            tasksList.appendChild(tr);
        });
    }

    renderDependencyCheckboxes() {
        const depsContainer = document.getElementById('task-dependencies');
        depsContainer.innerHTML = '';
        
        if (this.tasks.length === 0) {
            depsContainer.innerHTML = '<p class="hint-text">Сначала создайте задачи</p>';
            return;
        }
        
        // Фильтруем текущую задачу при редактировании
        const availableTasks = this.currentTask 
            ? this.tasks.filter(task => task.id !== this.currentTask.id)
            : this.tasks;
        
        if (availableTasks.length === 0) {
            depsContainer.innerHTML = '<p class="hint-text">Нет доступных задач для зависимостей</p>';
            return;
        }
        
        availableTasks.forEach(task => {
            const label = document.createElement('label');
            label.className = 'checkbox-label';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = task.id;
            checkbox.dataset.taskId = task.id;
            
            if (this.currentTask && this.currentTask.dependencies.includes(task.id)) {
                checkbox.checked = true;
            }
            
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(`${task.name} (ID: ${task.id})`));
            depsContainer.appendChild(label);
        });
    }

    renderResourceCheckboxes() {
        const resourcesContainer = document.getElementById('task-resources');
        resourcesContainer.innerHTML = '';
        
        if (this.resources.length === 0) {
            resourcesContainer.innerHTML = '<p class="hint-text">Сначала создайте ресурсы</p>';
            return;
        }
        
        this.resources.forEach(resource => {
            const wrapper = document.createElement('div');
            wrapper.className = 'resource-checkbox-item';
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = resource.id;
            checkbox.id = `resource-${resource.id}`;
            
            if (this.currentTask && this.currentTask.resource_ids.includes(resource.id)) {
                checkbox.checked = true;
            }
            
            // Вычислить остаток
            let remaining = resource.availability;
            if (resource.type === 'material') {
                const used = this.tasks.reduce((sum, task) => {
                    if (task.resource_ids && task.resource_ids.includes(resource.id)) {
                        const qty = (task.resource_quantities && task.resource_quantities[resource.id]) || 1;
                        return sum + qty;
                    }
                    return sum;
                }, 0);
                remaining = resource.availability - used;
            }
            
            const label = document.createElement('label');
            label.htmlFor = `resource-${resource.id}`;
            
            if (resource.type === 'material') {
                label.textContent = `${resource.name} (осталось: ${remaining})`;
            } else {
                label.textContent = `${resource.name} (доступно: ${resource.availability})`;
            }
            
            const quantityInput = document.createElement('input');
            quantityInput.type = 'number';
            quantityInput.min = 1;
            quantityInput.max = Math.max(1, remaining);
            quantityInput.value = (this.currentTask && this.currentTask.resource_quantities && this.currentTask.resource_quantities[resource.id]) || 1;
            quantityInput.id = `resource-quantity-${resource.id}`;
            quantityInput.disabled = !checkbox.checked;
            
            checkbox.addEventListener('change', () => {
                quantityInput.disabled = !checkbox.checked;
            });
            
            wrapper.appendChild(checkbox);
            wrapper.appendChild(label);
            wrapper.appendChild(quantityInput);
            resourcesContainer.appendChild(wrapper);
        });
    }

    async saveTask() {
        const name = document.getElementById('task-name').value.trim();
        const duration = parseInt(document.getElementById('task-duration').value);
        
        if (!name || !duration) {
            this.showNotification('Заполните название и длительность задачи', 'error');
            return;
        }
        
        const dependencies = Array.from(document.querySelectorAll('#task-dependencies input:checked'))
            .map(checkbox => parseInt(checkbox.value));
        
        const resourceQuantities = {};
        Array.from(document.querySelectorAll('#task-resources input[type="checkbox"]:checked'))
            .forEach(checkbox => {
                const resourceId = parseInt(checkbox.value);
                const quantityInput = document.getElementById(`resource-quantity-${resourceId}`);
                const quantity = quantityInput ? (parseInt(quantityInput.value) || 1) : 1;
                resourceQuantities[resourceId] = quantity;
            });
        
        // Валидация ресурсов
        for (const [resourceId, quantity] of Object.entries(resourceQuantities)) {
            const resource = this.resources.find(r => r.id === parseInt(resourceId));
            if (!resource) continue;
            
            if (resource.type === 'material') {
                const used = this.tasks.reduce((sum, task) => {
                    if (task.resource_ids && task.resource_ids.includes(resource.id)) {
                        const qty = (task.resource_quantities && task.resource_quantities[resource.id]) || 1;
                        return sum + qty;
                    }
                    return sum;
                }, 0);
                const remaining = resource.availability - used;
                
                if (quantity > remaining) {
                    this.showNotification(
                        `Недостаточно ресурса '${resource.name}': доступно ${remaining}, запрошено ${quantity}`,
                        'error'
                    );
                    return;
                }
            } else {
                if (quantity > resource.availability) {
                    this.showNotification(
                        `Недостаточно ресурса '${resource.name}': доступно ${resource.availability}, запрошено ${quantity}`,
                        'error'
                    );
                    return;
                }
            }
        }
        
        const taskData = {
            name,
            duration,
            dependencies,
            resource_ids: Object.keys(resourceQuantities).map(Number),
            resource_quantities: resourceQuantities
        };
        
        try {
            if (this.currentTask) {
                await this.apiRequest(`/api/tasks/${this.currentTask.id}`, 'PUT', taskData);
                this.showNotification('Задача обновлена', 'success');
            } else {
                await this.apiRequest(`/api/projects/${this.currentProject.id}/tasks`, 'POST', taskData);
                this.showNotification('Задача создана', 'success');
            }

            this.currentTask = null;
            document.getElementById('task-name').value = '';
            document.getElementById('task-duration').value = '';
            document.getElementById('cancel-task-edit').classList.add('hidden');
            document.getElementById('save-task-btn').textContent = 'Сохранить задачу';

            await this.loadTasks();
            await this.loadResources();
            this.loadTaskFormData();
            this.startPolling();

            
        } catch (error) {
            this.showError(error.message);
        }
    }

    editTask(taskId) {
        this.currentTask = this.tasks.find(task => task.id === taskId);
        
        document.getElementById('task-name').value = this.currentTask.name;
        document.getElementById('task-duration').value = this.currentTask.duration;
        
        document.getElementById('cancel-task-edit').classList.remove('hidden');
        document.getElementById('save-task-btn').textContent = 'Обновить задачу';
        
        this.renderDependencyCheckboxes();
        this.renderResourceCheckboxes();
    }

    cancelTaskEdit() {
        this.currentTask = null;
        document.getElementById('task-name').value = '';
        document.getElementById('task-duration').value = '';
        document.getElementById('cancel-task-edit').classList.add('hidden');
        document.getElementById('save-task-btn').textContent = 'Сохранить задачу';
        this.renderDependencyCheckboxes();
        this.renderResourceCheckboxes();
    }

    async deleteTask(taskId) {
        if (!confirm('Удалить задачу?')) return;
        
        try {
            await this.apiRequest(
                `/api/tasks/${taskId}`,
                'DELETE'
            );
            this.showNotification('Задача удалена', 'success');
            await this.loadTasks();
            this.loadTaskFormData();
            this.startPolling();
        } catch (error) {
            this.showError(error.message);
        }
    }

    // Ресурсы
    async loadResources() {
        if (!this.currentProject) return;
        
        try {
            const response = await this.apiRequest(`/api/projects/${this.currentProject.id}/resources`);
            this.resources = response.resources || [];
            this.renderResources();
            this.renderResourceCheckboxes();
        } catch (error) {
            console.error('Ошибка загрузки ресурсов:', error);
        }
    }

    renderResources() {
        const resourcesList = document.getElementById('resources-list');
        resourcesList.innerHTML = '';
        
        if (this.resources.length === 0) {
            resourcesList.innerHTML = '<tr><td colspan="5" style="text-align: center;">Нет ресурсов. Создайте первый ресурс.</td></tr>';
            return;
        }
        
        this.resources.forEach(resource => {
            const tr = document.createElement('tr');
            
            let displayAvailability = resource.availability;
            if (resource.type === 'material') {
                const used = this.tasks.reduce((sum, task) => {
                    if (task.resource_ids && task.resource_ids.includes(resource.id)) {
                        const qty = (task.resource_quantities && task.resource_quantities[resource.id]) || 1;
                        return sum + qty;
                    }
                    return sum;
                }, 0);
                displayAvailability = resource.availability - used;
            }
            
            tr.innerHTML = `
                <td>${resource.id}</td>
                <td>${resource.name}</td>
                <td>${resource.type === 'material' ? 'Материал' : resource.type === 'human' ? 'Человек' : 'Оборудование'}</td>
                <td>${resource.type === 'material' ? `${displayAvailability} (из ${resource.availability})` : resource.availability}</td>
                <td>
                    <button class="action-btn edit-btn" onclick="app.editResource(${resource.id})">Редактировать</button>
                    <button class="action-btn delete-btn" onclick="app.deleteResource(${resource.id})">Удалить</button>
                </td>
            `;
            
            resourcesList.appendChild(tr);
        });
    }

    async saveResource() {
        const name = document.getElementById('resource-name').value.trim();
        const type = document.getElementById('resource-type').value;
        const availability = parseInt(document.getElementById('resource-availability').value);
        
        if (!name || !availability) {
            this.showNotification('Заполните название и доступность ресурса', 'error');
            return;
        }
        
        const resourceData = {
            name,
            type,
            availability
        };
        
        try {
            if (this.isEditingResource && this.editingResourceId) {
                // Редактирование существующего ресурса
                await this.apiRequest(
                    `/api/resources/${this.editingResourceId}`,
                    'PUT',
                    resourceData
                );
                this.showNotification('Ресурс обновлен', 'success');
            } else {
                // Создание нового ресурса
                await this.apiRequest(
                    `/api/projects/${this.currentProject.id}/resources`,
                    'POST',
                    resourceData
                );
                this.showNotification('Ресурс сохранён', 'success');
            }
            
            // Очищаем форму
            this.cancelResourceEdit();
            
            // Обновляем список ресурсов
            await this.loadResources();
            
            // Обновляем чекбоксы в форме задачи
            this.renderResourceCheckboxes();
            this.loadTaskFormData();
            this.startPolling();

            
            console.log('Resource saved successfully');
        } catch (error) {
            console.error('Error saving resource:', error);
            this.showError(`Ошибка при сохранении ресурса: ${error.message}`);
        }
    }

    editResource(resourceId) {
        const resource = this.resources.find(r => r.id === resourceId);
        if (!resource) return;
        
        document.getElementById('resource-name').value = resource.name;
        document.getElementById('resource-type').value = resource.type;
        document.getElementById('resource-availability').value = resource.availability;
        
        this.isEditingResource = true;
        this.editingResourceId = resourceId;
        
        document.getElementById('save-resource-btn').textContent = 'Обновить ресурс';
        document.getElementById('cancel-resource-edit').classList.remove('hidden');
    }

    cancelResourceEdit() {
        this.isEditingResource = false;
        this.editingResourceId = null;
        
        document.getElementById('resource-name').value = '';
        document.getElementById('resource-type').value = 'human';
        document.getElementById('resource-availability').value = '';
        
        document.getElementById('save-resource-btn').textContent = 'Сохранить ресурс';
        document.getElementById('cancel-resource-edit').classList.add('hidden');
    }

    async deleteResource(resourceId) {
        if (!confirm('Удалить ресурс?')) return;
        
        try {
            await this.apiRequest(
                `/api/resources/${resourceId}`,
                'DELETE'
            );
            this.showNotification('Ресурс удален', 'success');
            await this.loadResources();
            this.renderResourceCheckboxes();
            this.startPolling();
        } catch (error) {
            this.showError(error.message);
        }
    }

    // План и диаграмма Ганта
    async calculatePlan() {
        if (!this.currentProject) return;
        
        try {
            // Сбросить предыдущую ошибку
            this.planData = null;
            document.getElementById('gantt-chart').innerHTML = '<p class="no-plan-message">Запуск расчёта...</p>';
            
            this.updatePlanStatus('pending');
            
            const response = await this.apiRequest(
                `/api/projects/${this.currentProject.id}/plan/calculate`,
                'POST'
            );
            
            console.log('Plan calculation started:', response);
            
            // Запускаем polling для отслеживания статуса
            this.startPolling();
        } catch (error) {
            console.error('Error calculating plan:', error);
            this.updatePlanStatus('error', error.message);
        }
    }

    

    startPolling() {
        this.stopPolling();
        console.log('Starting polling for plan status...');
        
        // Немедленно проверяем статус
        this.pollPlanStatus();
        
        // Запускаем периодический опрос
        this.pollingInterval = setInterval(() => {
            this.pollPlanStatus();
        }, 2000);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            console.log('Polling stopped');
        }
    }

    
    async pollPlanStatus() {
        if (!this.currentProject) {
            this.stopPolling();
            return;
        }
        
        try {
            const plan = await this.apiRequest(`/api/projects/${this.currentProject.id}/plan/latest`);
            
            if (plan && plan.project_id && plan.project_id !== this.currentProject.id) {
                console.warn('Plan project mismatch:', plan.project_id, 'vs', this.currentProject.id);
                this.planData = null;
                this.updatePlanStatus('error', 'Несоответствие данных');
                this.stopPolling();
                return;
            }
            
            this.updatePlanStatus(plan.status);
            
            if (plan.status === 'done' && plan.data) {
                this.stopPolling();
                this.planData = plan.data;
                
                // Загрузить задачи, если их нет
                if (this.tasks.length === 0 && this.currentProject) {
                    await this.loadTasks();
                }
                
                // Сохранить для конкретного проекта
                localStorage.setItem(`plan_${this.currentProject.id}`, JSON.stringify(plan.data));
                localStorage.setItem(`tasks_${this.currentProject.id}`, JSON.stringify(this.tasks));
                localStorage.setItem(`planStatus_${this.currentProject.id}`, 'done');
                
                const conflictContainer = document.getElementById('conflict-graph-container');
                if (conflictContainer) {
                    conflictContainer.classList.add('hidden');
                }
                
                const ganttChart = document.getElementById('gantt-chart');
                if (ganttChart) {
                    ganttChart.classList.remove('hidden');
                }
                
                this.renderGanttChart(plan.data, false);
                this.updatePlanStatus('done');
                this.showNotification('План рассчитан', 'success');
                
            } else if (plan.status === 'error') {
                this.stopPolling();
                this.updatePlanStatus('error', plan.data?.error || 'Ошибка расчета плана');
                
                // Загрузить задачи, если их нет
                if (this.tasks.length === 0 && this.currentProject) {
                    await this.loadTasks();
                }
                
                // Сохранить для конкретного проекта
                localStorage.setItem(`planStatus_${this.currentProject.id}`, 'error');
                
                const ganttChart = document.getElementById('gantt-chart');
                if (ganttChart) {
                    ganttChart.classList.add('hidden');
                }
                
                const conflictContainer = document.getElementById('conflict-graph-container');
                if (conflictContainer) {
                    conflictContainer.classList.remove('hidden');
                }
                
                this.renderDependencyGraph('conflict-graph');
            }
        } catch (error) {
            console.error('Error polling plan status:', error);
        }
    }
    async loadLatestPlan() {
        if (!this.currentProject) {
            console.warn('No current project selected');
            return;
        }
        
        // ✅ ОЧИЩАЕМ СТАРЫЙ ПЛАН ПЕРЕД ЗАГРУЗКОЙ
        this.planData = null;
        const ganttChart = document.getElementById('gantt-chart');
        if (ganttChart) {
            ganttChart.innerHTML = '<p class="no-plan-message">Загрузка плана...</p>';
        }
        
        try {
            const response = await this.apiRequest(`/api/projects/${this.currentProject.id}/plan/latest`);
            
            // ✅ ПРОВЕРКА ПРИНАДЛЕЖНОСТИ ПЛАНА
            if (response && response.project_id && response.project_id !== this.currentProject.id) {
                console.warn('⚠️ Plan project mismatch:', response.project_id, 'vs', this.currentProject.id);
                this.updatePlanStatus('error', 'Несоответствие данных');
                if (ganttChart) {
                    ganttChart.innerHTML = '<p class="no-plan-message" style="color: #e74c3c;">⚠️ Ошибка: данные плана принадлежат другому проекту</p>';
                }
                return;
            }
            
            this.updatePlanStatus(response.status);
            
            if (response.status === 'done' && response.data) {
                this.stopPolling();
                this.planData = response.data;
                this.renderGanttChart(response.data);
                this.updatePlanStatus('done');
            } else if (response.status === 'error') {
                this.stopPolling();
                this.updatePlanStatus('error', response.message || 'Ошибка расчета плана');
                if (ganttChart) {
                    ganttChart.innerHTML = `<p class="no-plan-message" style="color: #e74c3c;">⚠️ ${response.message || 'Ошибка расчета плана'}</p>`;
                }
            } else if (response.status === 'pending' || response.status === 'calculating') {
                this.startPolling();
            }
        } catch (error) {
            console.error('Error loading latest plan:', error);
            // Если план не найден (404) - это нормально
            if (error.message && error.message.includes('404')) {
                if (ganttChart) {
                    ganttChart.innerHTML = '<p class="no-plan-message">План не рассчитан. Нажмите "Пересчитать план"</p>';
                }
                this.updatePlanStatus('pending', 'Нет плана');
            } else {
                if (ganttChart) {
                    ganttChart.innerHTML = `<p class="no-plan-message" style="color: #e74c3c;">⚠️ Ошибка загрузки плана: ${error.message}</p>`;
                }
                this.updatePlanStatus('error', error.message);
            }
        }
    }


    updatePlanStatus(status, message = '') {
        const statusEl = document.getElementById('plan-status');
        const statusText = document.getElementById('plan-status-text');
        
        if (!statusEl || !statusText) {
            console.warn('Plan status elements not found');
            return;
        }
        
        statusEl.className = `plan-status ${status}`;
        
        const statusMessages = {
            pending: 'Ожидание',
            calculating: 'Расчёт...',
            done: 'Готово',
            error: 'Ошибка'
        };
        
        const statusMessage = statusMessages[status] || status;
        statusText.textContent = `Статус: ${statusMessage}${message ? ` - ${message}` : ''}`;
        
        console.log('Plan status updated:', status, message);
    }


    renderGanttChart(planData, hasConflict = false) {
        const ganttChart = document.getElementById('gantt-chart');
        ganttChart.innerHTML = '';
        
        if (!planData || !planData.tasks || planData.tasks.length === 0) {
            ganttChart.innerHTML = '<p class="no-plan-message">Нет данных для отображения</p>';
            return;
        }
        
        const validTasks = planData.tasks.filter(pt => 
            this.tasks.some(t => t.id === pt.task_id)
        );
        
        if (validTasks.length === 0) {
            ganttChart.innerHTML = '<p class="no-plan-message">Нет задач для отображения</p>';
            return;
        }
        
        // Определить конфликты (пересечение по времени + общие ресурсы)
        const conflicts = new Set();
        if (hasConflict) {
            for (let i = 0; i < validTasks.length; i++) {
                for (let j = i + 1; j < validTasks.length; j++) {
                    const a = validTasks[i];
                    const b = validTasks[j];
                    const timeOverlap = a.start_time < b.end_time && b.start_time < a.end_time;
                    
                    const taskA = this.tasks.find(t => t.id === a.task_id);
                    const taskB = this.tasks.find(t => t.id === b.task_id);
                    const sharedResources = (taskA?.resource_ids || []).filter(id => 
                        (taskB?.resource_ids || []).includes(id)
                    );
                    
                    if (timeOverlap && sharedResources.length > 0) {
                        conflicts.add(a.task_id);
                        conflicts.add(b.task_id);
                    }
                }
            }
        }
        
        // Предупреждение о конфликтах
        if (hasConflict && conflicts.size > 0) {
            const warning = document.createElement('div');
            warning.style.cssText = `
                background: #f8d7da;
                color: #721c24;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 15px;
                font-weight: bold;
                text-align: center;
            `;
            warning.textContent = '⚠️ План построить невозможно из-за конфликтов ресурсов';
            ganttChart.appendChild(warning);
        }
        
        let minTime = Math.min(...validTasks.map(t => t.start_time));
        let maxTime = Math.max(...validTasks.map(t => t.end_time));
        
        if (maxTime === minTime) maxTime = minTime + 60;
        
        const timeRange = maxTime - minTime;
        const LABEL_WIDTH = 140;
        const hourStep = 60;
        const numHours = Math.ceil(timeRange / hourStep);
        
        // Контейнер
        const ganttContainer = document.createElement('div');
        ganttContainer.style.cssText = `
            position: relative;
            padding-left: ${LABEL_WIDTH}px;
        `;
        
        // Заголовок шкалы
        const timelineHeader = document.createElement('div');
        timelineHeader.style.cssText = `
            position: relative;
            height: 30px;
            border-bottom: 1px solid #ddd;
            margin-bottom: 10px;
        `;
        
        // Вертикальные направляющие в заголовке
        for (let hour = 0; hour <= numHours; hour++) {
            const time = minTime + hour * hourStep;
            const leftPercent = ((time - minTime) / timeRange) * 100;
            
            const guideLine = document.createElement('div');
            guideLine.style.cssText = `
                position: absolute;
                left: ${leftPercent}%;
                top: 0;
                bottom: 0;
                width: 1px;
                background: ${hour === 0 ? '#ccc' : '#e0e0e0'};
            `;
            timelineHeader.appendChild(guideLine);
            
            const marker = document.createElement('span');
            marker.style.cssText = `
                position: absolute;
                left: ${leftPercent}%;
                top: 5px;
                transform: translateX(-50%);
                font-size: 11px;
                color: #666;
                white-space: nowrap;
            `;
            
            const hours = Math.floor(time / 60);
            const minutes = Math.round(time % 60);
            marker.textContent = minutes > 0 ? `${hours}ч ${minutes}м` : `${hours}ч`;
            
            timelineHeader.appendChild(marker);
        }
        
        ganttContainer.appendChild(timelineHeader);
        
        // Строка с общим временем
        const totalTimeDiv = document.createElement('div');
        totalTimeDiv.style.cssText = `
            text-align: right;
            font-size: 13px;
            color: #555;
            margin-bottom: 10px;
            font-weight: bold;
        `;
        
        const totalMinutes = timeRange;
        const totalHours = Math.floor(totalMinutes / 60);
        const remainingMinutes = Math.round(totalMinutes % 60);
        totalTimeDiv.textContent = `Общее время: ${totalHours} часов ${remainingMinutes} минут`;
        
        ganttContainer.appendChild(totalTimeDiv);
        
        // Полоски задач
        validTasks.forEach(planTask => {
            const task = this.tasks.find(t => t.id === planTask.task_id);
            
            const row = document.createElement('div');
            row.style.cssText = `
                display: flex;
                align-items: center;
                height: 40px;
                margin-bottom: 5px;
                position: relative;
            `;
            
            const taskName = document.createElement('div');
            taskName.style.cssText = `
                position: absolute;
                left: -${LABEL_WIDTH}px;
                width: ${LABEL_WIDTH - 10}px;
                font-size: 13px;
                font-weight: bold;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                text-align: right;
                padding-right: 10px;
            `;
            taskName.textContent = task.name;
            taskName.title = task.name;
            
            const timeline = document.createElement('div');
            timeline.style.cssText = `
                position: relative;
                flex: 1;
                height: 30px;
                background: #f5f5f5;
                border-radius: 4px;
                overflow: visible;
            `;
            
            // Вертикальные направляющие в таймлайне
            for (let hour = 0; hour <= numHours; hour++) {
                const time = minTime + hour * hourStep;
                const leftPercent = ((time - minTime) / timeRange) * 100;
                
                const guideLine = document.createElement('div');
                guideLine.style.cssText = `
                    position: absolute;
                    left: ${leftPercent}%;
                    top: -10px;
                    bottom: -10px;
                    width: 1px;
                    background: #e8e8e8;
                    z-index: 1;
                `;
                timeline.appendChild(guideLine);
            }
            
            // Полоска задачи
            const bar = document.createElement('div');
            const startPercent = ((planTask.start_time - minTime) / timeRange) * 100;
            const widthPercent = ((planTask.end_time - planTask.start_time) / timeRange) * 100;
            
            const durationMinutes = planTask.end_time - planTask.start_time;
            const durationHours = durationMinutes / 60;
            
            bar.style.cssText = `
                position: absolute;
                left: ${startPercent}%;
                width: ${Math.max(0.5, widthPercent)}%;
                height: 100%;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.2s;
                z-index: 2;
            `;
            
            // Подсветка конфликтов
            if (conflicts.has(planTask.task_id)) {
                bar.style.background = 'linear-gradient(135deg, #e74c3c, #c0392b)';
                bar.style.boxShadow = '0 0 8px rgba(231, 76, 60, 0.5)';
            } else {
                bar.style.background = 'linear-gradient(135deg, #667eea, #764ba2)';
            }
            
            bar.title = `${task.name}\nНачало: ${Math.floor(planTask.start_time/60)}ч ${Math.round(planTask.start_time%60)}м\nКонец: ${Math.floor(planTask.end_time/60)}ч ${Math.round(planTask.end_time%60)}м\nДлительность: ${durationMinutes} мин (${durationHours.toFixed(1)} ч)`;
            
            timeline.appendChild(bar);
            row.appendChild(taskName);
            row.appendChild(timeline);
            ganttContainer.appendChild(row);
        });
        
        ganttChart.appendChild(ganttContainer);
        this.renderDependencyGraph('plan-graph');
    }

    renderDependencyGraph(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = '';
        
        if (!this.tasks || this.tasks.length === 0) {
            container.innerHTML = '<p class="hint-text">Нет задач для отображения</p>';
            return;
        }
        
        const taskMap = {};
        this.tasks.forEach(task => { taskMap[task.id] = task; });
        
        const dependencies = [];
        this.tasks.forEach(task => {
            (task.dependencies || []).forEach(depId => {
                if (taskMap[depId]) {
                    dependencies.push({ from: depId, to: task.id });
                }
            });
        });
        
        // Показываем ВСЕ задачи как конфликтные
        const graphWrapper = document.createElement('div');
        graphWrapper.style.cssText = `
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            justify-content: center;
            padding: 20px;
        `;
        
        this.tasks.forEach(task => {
            const node = document.createElement('div');
            node.className = 'graph-node graph-conflict';
            node.textContent = task.name;
            node.style.cssText = `
                padding: 12px 20px;
                background: linear-gradient(135deg, #e74c3c, #c0392b);
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
                cursor: pointer;
                box-shadow: 0 2px 8px rgba(231, 76, 60, 0.3);
                transition: all 0.2s;
                position: relative;
            `;
            
            // Добавить значок конфликта
            const badge = document.createElement('span');
            badge.textContent = '⚠️';
            badge.style.cssText = `
                position: absolute;
                top: -8px;
                right: -8px;
                font-size: 16px;
            `;
            node.appendChild(badge);
            
            node.addEventListener('mouseenter', () => {
                node.style.transform = 'scale(1.05)';
                node.style.boxShadow = '0 4px 12px rgba(231, 76, 60, 0.5)';
            });
            node.addEventListener('mouseleave', () => {
                node.style.transform = 'scale(1)';
                node.style.boxShadow = '0 2px 8px rgba(231, 76, 60, 0.3)';
            });
            
            graphWrapper.appendChild(node);
        });
        
        container.appendChild(graphWrapper);
    }

    clearPlanCache() {
        this.planData = null;
        this.stopPolling();
        
        const ganttChart = document.getElementById('gantt-chart');
        if (ganttChart) {
            ganttChart.innerHTML = '<p class="no-plan-message">Запустите расчет плана для отображения диаграммы Ганта</p>';
        }
        
        const statusEl = document.getElementById('plan-status');
        const statusText = document.getElementById('plan-status-text');
        if (statusEl && statusText) {
            statusEl.className = 'plan-status';
            statusText.textContent = 'Статус: нет плана';
        }
    }
}

// Создание экземпляра приложения
const app = new ProjectPlanner();
window.app = app;
