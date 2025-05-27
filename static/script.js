document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const generateBtn = document.getElementById('generateBtn');
    const daysInput = document.getElementById('days');
    const hoursInput = document.getElementById('hours');
    const emailInput = document.getElementById('email');
    const whatsappInput = document.getElementById('whatsapp');
    const chatMessages = document.getElementById('chatMessages');
    const chatInput = document.getElementById('chatInput');
    const sendMessageBtn = document.getElementById('sendMessage');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const studyPlan = document.getElementById('studyPlan');
    const downloadPdfBtn = document.getElementById('downloadPdf');

    // Initialize calendar
    let calendar;
    let currentPlan = null;
    let selectedFiles = [];

    // Initialize the calendar
    function initCalendar() {
        const calendarEl = document.getElementById('calendar');
        calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek'
            },
            events: [],
            eventClick: function(info) {
                showStudyDetails(info.event);
            },
            eventDidMount: function(info) {
                info.el.setAttribute('title', info.event.title);
            }
        });
        calendar.render();
    }

    // Show study details in a modal
    function showStudyDetails(event) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>${event.title}</h3>
                <p>Date: ${event.start.toLocaleDateString()}</p>
                <div class="study-details">
                    ${event.extendedProps.details || 'No additional details available.'}
                </div>
                <button onclick="this.parentElement.parentElement.remove()">Close</button>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Update calendar with study plan
    function updateCalendar(plan) {
        const events = [];
        plan.study_plan.forEach((day, index) => {
            const date = new Date();
            date.setDate(date.getDate() + index);
            
            day.topics.forEach(topic => {
                events.push({
                    title: topic.name,
                    start: date,
                    allDay: true,
                    backgroundColor: getRandomColor(),
                    details: `Hours: ${topic.hours}\nTopics: ${topic.name}`
                });
            });
        });
        
        calendar.removeAllEvents();
        calendar.addEventSource(events);
    }

    // Display study plan
    function displayStudyPlan(plan) {
        studyPlan.innerHTML = '';
        currentPlan = plan;
        
        plan.study_plan.forEach((day, index) => {
            const dayElement = document.createElement('div');
            dayElement.className = 'study-day';
            
            const date = new Date();
            date.setDate(date.getDate() + index);
            
            // Calculate total hours for the day
            const totalHours = day.topics.reduce((sum, topic) => sum + topic.hours, 0);
            
            // Create day status
            const dayStatus = document.createElement('div');
            dayStatus.className = 'day-status';
            dayStatus.textContent = 'Upcoming';
            
            // Create progress bar
            const progressBar = document.createElement('div');
            progressBar.className = 'study-progress';
            progressBar.innerHTML = `
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
            `;
            
            dayElement.innerHTML = `
                <h3>${day.day} - ${date.toLocaleDateString()}</h3>
                ${day.topics.map(topic => `
                    <div class="topic-item">
                        <span>${topic.name}</span>
                        <span>${formatHoursMinutes(topic.hours)}</span>
                        <div class="topic-tags">
                            ${getTopicTags(topic.name)}
                        </div>
                    </div>
                `).join('')}
            `;
            
            // Add status and progress bar
            dayElement.insertBefore(dayStatus, dayElement.firstChild);
            dayElement.appendChild(progressBar);
            
            // Add hover effect for topic items
            const topicItems = dayElement.querySelectorAll('.topic-item');
            topicItems.forEach(item => {
                item.addEventListener('mouseenter', () => {
                    item.style.transform = 'translateX(5px)';
                });
                item.addEventListener('mouseleave', () => {
                    item.style.transform = 'translateX(0)';
                });
            });
            
            studyPlan.appendChild(dayElement);
        });

        // Show download button if PDF URL is available
        if (plan.pdf_url) {
            downloadPdfBtn.style.display = 'block';
            downloadPdfBtn.onclick = () => {
                window.location.href = plan.pdf_url;
            };
        }
    }

    // Helper function to generate random colors
    function getRandomColor() {
        const colors = [
            '#4299e1', '#48bb78', '#ed8936', '#e53e3e',
            '#805ad5', '#d69e2e', '#38b2ac', '#f56565'
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    // Helper function to generate topic tags
    function getTopicTags(topicName) {
        const tags = [];
        const topicLower = topicName.toLowerCase();
        
        if (topicLower.includes('algorithm')) {
            tags.push('Algorithm');
        }
        if (topicLower.includes('search')) {
            tags.push('Search');
        }
        if (topicLower.includes('sort')) {
            tags.push('Sort');
        }
        if (topicLower.includes('graph')) {
            tags.push('Graph');
        }
        if (topicLower.includes('recursion')) {
            tags.push('Recursion');
        }
        if (topicLower.includes('dynamic')) {
            tags.push('Dynamic Programming');
        }
        if (topicLower.includes('greedy')) {
            tags.push('Greedy');
        }
        
        return tags.map(tag => `<span class="topic-tag">${tag}</span>`).join('');
    }

    // File upload handling
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) {
            selectedFiles = Array.from(files);
            showSelectedFiles();
            generateBtn.disabled = false;
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length) {
            selectedFiles = Array.from(e.target.files);
            showSelectedFiles();
            generateBtn.disabled = false;
        }
    });

    function showSelectedFiles() {
        // Remove previous file messages
        const prev = document.querySelectorAll('.selected-file-message');
        prev.forEach(el => el.remove());
        selectedFiles.forEach(file => {
            const msg = document.createElement('div');
            msg.className = 'message bot selected-file-message';
            msg.textContent = 'File selected: ' + file.name;
            chatMessages.appendChild(msg);
        });
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Form submission
    generateBtn.addEventListener('click', async () => {
        const whatsappRaw = whatsappInput.value.trim();
        if (!/^[0-9]{10}$/.test(whatsappRaw)) {
            addMessage('Please enter a valid 10-digit mobile number for WhatsApp.', 'bot');
            return;
        }
        const whatsappNumber = `+91${whatsappRaw}`;
        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('file', file);
        });
        formData.append('days', daysInput.value);
        formData.append('hours', hoursInput.value);
        formData.append('email', emailInput.value);
        formData.append('whatsapp_number', whatsappNumber);

        showLoading(true);
        addMessage('Generating your study plan...', 'bot');

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                updateCalendar(data);
                displayStudyPlan(data);
                addMessage('Your study plan has been generated!', 'bot');
                addMessage('You can ask me questions about your study plan or request adjustments.', 'bot');
            } else {
                addMessage('Error: ' + data.error, 'bot');
            }
        } catch (error) {
            addMessage('An error occurred while generating the study plan.', 'bot');
        } finally {
            showLoading(false);
        }
    });

    // Chat functionality
    sendMessageBtn.addEventListener('click', handleChatMessage);
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleChatMessage();
        }
    });

    async function handleChatMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        chatInput.value = '';

        // Show typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'message bot typing';
        typingIndicator.textContent = '...';
        chatMessages.appendChild(typingIndicator);

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message,
                    study_plan: currentPlan
                })
            });

            const data = await response.json();
            typingIndicator.remove();

            if (response.ok) {
                addMessage(data.response, 'bot');
                
                // If the plan was updated
                if (data.updated_plan) {
                    currentPlan = data.updated_plan;
                    updateCalendar(currentPlan);
                    displayStudyPlan(currentPlan);
                }
            } else {
                addMessage('Error: ' + data.error, 'bot');
            }
        } catch (error) {
            typingIndicator.remove();
            addMessage('Sorry, I encountered an error. Please try again.', 'bot');
        }
    }

    // Helper functions
    function addMessage(text, type) {
        const message = document.createElement('div');
        message.className = `message ${type}`;
        message.textContent = text;
        chatMessages.appendChild(message);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function showLoading(show) {
        loadingOverlay.style.display = show ? 'flex' : 'none';
    }

    function formatHoursMinutes(hours) {
        const h = Math.floor(hours);
        const m = Math.round((hours - h) * 60);
        let result = '';
        if (h > 0) result += `${h} hour${h > 1 ? 's' : ''}`;
        if (m > 0) result += (result ? ' ' : '') + `${m} minute${m > 1 ? 's' : ''}`;
        if (!result) result = '0 minutes';
        return result;
    }

    // Initialize components
    initCalendar();
}); 