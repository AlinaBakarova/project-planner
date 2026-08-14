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
        this.apiBaseUrl = 'http://localhost:8000'; // Базовый URL для API
        
        this.init();
    }

    init() {
        this.bindEvents();
        if (this.token) {
            this.showMainScreen();
            this.loadProjects();
        } else {
            this.showAuthScreen();
        }
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

        // Задачи
        document.getElementById('save-task-btn').addEventListener('click', () => this.saveTask());
        document.getElementById('cancel-task-edit').addEventListener('click', () => this.cancelTaskEdit());

        // Ресурсы
        document.getElementById('save-resource-btn').addEventListener('click', () => this.saveResource());

        // План
        document.getElementById('calculate-plan-btn').addEventListener('click', () => this.calculatePlan());
    }

    // API запросы с полными URL
    async apiRequest(endpoint, method = 'GET', body = null) {
        const url = `${this.apiBaseUrl}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
        };

        if (this.token) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }

        const options = {
            method,
            headers,
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            console.log(`Making ${method} request to: ${url}`);
            
            const response = await fetch(url, options);
            
            console.log('Response status:', response.status);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({
                    detail: `HTTP ${response.status}: ${response.statusText}`
                }));
                
                console.error('API Error:', errorData);
                throw new Error(errorData.detail || errorData.message || 'Ошибка запроса');
            }

            const data = await response.json();
            console.log('Response data:', data);
            return data;
        } catch (error) {
            console.error('API Request Error:', error);
            
            // Более понятные сообщения об ошибках
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
        
        document.querySelectorAll('.project-view .tabs .tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tab);
        });
        
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tab}-tab`);
        });
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
        this.token = null;
        this.currentUser = null;
        this.currentProject = null;
        this.tasks = [];
        this.resources = [];
        this.planData = null;
        
        localStorage.removeItem('token');
        localStorage.removeItem('currentUser');
        
        this.showAuthScreen();
        
        document.getElementById('login-form').reset();
        document.getElementById('register-form').reset();
        this.clearAuthMessage();
    }

    // Проекты
    async loadProjects() {
        try {
            const response = await this.apiRequest('/api/projects');
            const projects = response.projects || [];
            this.renderProjects(projects);
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
            alert('Введите название проекта');
            return;
        }

        try {
            const project = await this.apiRequest('/api/projects', 'POST', { name });
            document.getElementById('new-project-name').value = '';
            await this.loadProjects();
            await this.selectProject(project);
        } catch (error) {
            alert(error.message);
        }
    }

    async selectProject(project) {
        this.currentProject = project;
        this.currentTask = null;
        
        document.getElementById('no-project-selected').classList.add('hidden');
        document.getElementById('project-view').classList.remove('hidden');
        document.getElementById('project-name').textContent = project.name;
        
        document.querySelectorAll('.projects-list li').forEach(li => {
            li.classList.toggle('active', li.dataset.projectId == project.id);
        });
        
        await Promise.all([
            this.loadTasks(),
            this.loadResources(),
            this.loadLatestPlan()
        ]);
    }

    // Задачи
    async loadTasks() {
        if (!this.currentProject) return;
        
        try {
            const response = await this.apiRequest(`/api/projects/${this.currentProject.id}/tasks`);
            this.tasks = response.tasks || [];
            this.renderTasks();
            this.renderDependenciesCheckboxes();
            this.renderResourcesCheckboxes();
        } catch (error) {
            console.error('Ошибка загрузки задач:', error);
        }
    }

    renderTasks() {
        const tasksList = document.getElementById('tasks-list');
        tasksList.innerHTML = '';
        
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

    renderDependenciesCheckboxes() {
        const depsContainer = document.getElementById('task-dependencies');
        depsContainer.innerHTML = '';
        
        this.tasks.forEach(task => {
            if (this.currentTask && task.id === this.currentTask.id) return;
            
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = task.id;
            checkbox.dataset.taskId = task.id;
            
            if (this.currentTask && this.currentTask.dependencies.includes(task.id)) {
                checkbox.checked = true;
            }
            
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(task.name));
            depsContainer.appendChild(label);
        });
    }

    renderResourcesCheckboxes() {
        const resourcesContainer = document.getElementById('task-resources');
        resourcesContainer.innerHTML = '';
        
        this.resources.forEach(resource => {
            const label = document.createElement('label');
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = resource.id;
            checkbox.dataset.resourceId = resource.id;
            
            if (this.currentTask && this.currentTask.resource_ids.includes(resource.id)) {
                checkbox.checked = true;
            }
            
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(resource.name));
            resourcesContainer.appendChild(label);
        });
    }

    async saveTask() {
        const name = document.getElementById('task-name').value.trim();
        const duration = parseInt(document.getElementById('task-duration').value);
        
        if (!name || !duration) {
            alert('Заполните название и длительность задачи');
            return;
        }
        
        const dependencies = Array.from(document.querySelectorAll('#task-dependencies input:checked'))
            .map(checkbox => parseInt(checkbox.value));
        
        const resourceIds = Array.from(document.querySelectorAll('#task-resources input:checked'))
            .map(checkbox => parseInt(checkbox.value));
        
        const taskData = {
            name,
            duration,
            dependencies,
            resource_ids: resourceIds
        };
        
        try {
            if (this.currentTask) {
                await this.apiRequest(
                    `/api/projects/${this.currentProject.id}/tasks/${this.currentTask.id}`,
                    'PUT',
                    taskData
                );
            } else {
                await this.apiRequest(
                    `/api/projects/${this.currentProject.id}/tasks`,
                    'POST',
                    taskData
                );
            }
            
            this.cancelTaskEdit();
            await this.loadTasks();
        } catch (error) {
            alert(error.message);
        }
    }

    editTask(taskId) {
        this.currentTask = this.tasks.find(task => task.id === taskId);
        
        document.getElementById('task-name').value = this.currentTask.name;
        document.getElementById('task-duration').value = this.currentTask.duration;
        
        document.getElementById('cancel-task-edit').classList.remove('hidden');
        document.getElementById('save-task-btn').textContent = 'Обновить задачу';
        
        this.renderDependenciesCheckboxes();
        this.renderResourcesCheckboxes();
    }

    cancelTaskEdit() {
        this.currentTask = null;
        document.getElementById('task-name').value = '';
        document.getElementById('task-duration').value = '';
        document.getElementById('cancel-task-edit').classList.add('hidden');
        document.getElementById('save-task-btn').textContent = 'Сохранить задачу';
        this.renderDependenciesCheckboxes();
        this.renderResourcesCheckboxes();
    }

    async deleteTask(taskId) {
        if (!confirm('Удалить задачу?')) return;
        
        try {
            await this.apiRequest(
                `/api/projects/${this.currentProject.id}/tasks/${taskId}`,
                'DELETE'
            );
            await this.loadTasks();
        } catch (error) {
            alert(error.message);
        }
    }

    // Ресурсы
    async loadResources() {
        if (!this.currentProject) return;
        
        try {
            const response = await this.apiRequest(`/api/projects/${this.currentProject.id}/resources`);
            this.resources = response.resources || [];
            this.renderResources();
            this.renderResourcesCheckboxes();
        } catch (error) {
            console.error('Ошибка загрузки ресурсов:', error);
        }
    }

    renderResources() {
        const resourcesList = document.getElementById('resources-list');
        resourcesList.innerHTML = '';
        
        this.resources.forEach(resource => {
            const tr = document.createElement('tr');
            
            tr.innerHTML = `
                <td>${resource.id}</td>
                <td>${resource.name}</td>
                <td>${resource.type}</td>
                <td>${resource.availability}</td>
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
            alert('Заполните название и доступность ресурса');
            return;
        }
        
        try {
            await this.apiRequest(
                `/api/projects/${this.currentProject.id}/resources`,
                'POST',
                { name, type, availability }
            );
            
            document.getElementById('resource-name').value = '';
            document.getElementById('resource-availability').value = '';
            
            await this.loadResources();
        } catch (error) {
            alert(error.message);
        }
    }

    editResource(resourceId) {
        const resource = this.resources.find(r => r.id === resourceId);
        document.getElementById('resource-name').value = resource.name;
        document.getElementById('resource-type').value = resource.type;
        document.getElementById('resource-availability').value = resource.availability;
    }

    async deleteResource(resourceId) {
        if (!confirm('Удалить ресурс?')) return;
        
        try {
            await this.apiRequest(
                `/api/projects/${this.currentProject.id}/resources/${resourceId}`,
                'DELETE'
            );
            await this.loadResources();
        } catch (error) {
            alert(error.message);
        }
    }

    // План и диаграмма Ганта
    async calculatePlan() {
        if (!this.currentProject) return;
        
        try {
            const response = await this.apiRequest(
                `/api/projects/${this.currentProject.id}/plan/calculate`,
                'POST'
            );
            
            this.updatePlanStatus(response.status);
            this.startPolling();
        } catch (error) {
            this.updatePlanStatus('error', error.message);
        }
    }

    startPolling() {
        this.stopPolling();
        this.pollingInterval = setInterval(() => this.loadLatestPlan(), 2000);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    async loadLatestPlan() {
        if (!this.currentProject) return;
        
        try {
            const response = await this.apiRequest(`/api/projects/${this.currentProject.id}/plan/latest`);
            
            this.updatePlanStatus(response.status);
            
            if (response.status === 'done' && response.data) {
                this.stopPolling();
                this.planData = response.data;
                this.renderGanttChart(response.data);
            } else if (response.status === 'error') {
                this.stopPolling();
                this.updatePlanStatus('error', response.message || 'Ошибка расчета плана');
            }
        } catch (error) {
            this.stopPolling();
            this.updatePlanStatus('error', error.message);
        }
    }

    updatePlanStatus(status, message = '') {
        const statusEl = document.getElementById('plan-status');
        const statusText = document.getElementById('plan-status-text');
        
        statusEl.className = `plan-status ${status}`;
        
        const statusMessages = {
            pending: 'Статус: ожидание',
            calculating: 'Статус: расчет...',
            done: 'Статус: готово',
            error: `Статус: ошибка - ${message}`
        };
        
        statusText.textContent = statusMessages[status] || `Статус: ${status}`;
    }

    renderGanttChart(planData) {
        const ganttChart = document.getElementById('gantt-chart');
        ganttChart.innerHTML = '';
        
        if (!planData.tasks || planData.tasks.length === 0) {
            ganttChart.innerHTML = '<p class="no-plan-message">Нет данных для отображения</p>';
            return;
        }
        
        const maxTime = Math.max(...planData.tasks.map(task => task.end_time));
        const minTime = Math.min(...planData.tasks.map(task => task.start_time));
        const timeRange = maxTime - minTime || 1;
        
        // Заголовок временной шкалы
        const timelineHeader = document.createElement('div');
        timelineHeader.className = 'gantt-timeline-header';
        
        const numMarkers = Math.min(10, Math.ceil(timeRange / 60));
        for (let i = 0; i <= numMarkers; i++) {
            const time = minTime + (timeRange * i / numMarkers);
            const position = 150 + ((time - minTime) / timeRange) * 500;
            
            const marker = document.createElement('span');
            marker.className = 'gantt-timeline-marker';
            marker.style.left = `${position}px`;
            marker.textContent = `${Math.round(time / 60)}ч`;
            timelineHeader.appendChild(marker);
        }
        
        ganttChart.appendChild(timelineHeader);
        
        // Задачи
        planData.tasks.forEach(planTask => {
            const task = this.tasks.find(t => t.id === planTask.task_id);
            if (!task) return;
            
            const row = document.createElement('div');
            row.className = 'gantt-row';
            
            const taskName = document.createElement('div');
            taskName.className = 'gantt-task-name';
            taskName.textContent = task.name;
            
            const timeline = document.createElement('div');
            timeline.className = 'gantt-timeline';
            
            const bar = document.createElement('div');
            bar.className = 'gantt-bar';
            
            const startPercent = ((planTask.start_time - minTime) / timeRange) * 100;
            const widthPercent = ((planTask.end_time - planTask.start_time) / timeRange) * 100;
            
            bar.style.left = `${startPercent}%`;
            bar.style.width = `${widthPercent}%`;
            bar.title = `${task.name}: ${planTask.start_time}-${planTask.end_time} мин`;
            
            timeline.appendChild(bar);
            row.appendChild(taskName);
            row.appendChild(timeline);
            ganttChart.appendChild(row);
        });
    }
}

// Создание экземпляра приложения
const app = new ProjectPlanner();
window.app = app; // Делаем доступным глобально для onclick обработчиков
