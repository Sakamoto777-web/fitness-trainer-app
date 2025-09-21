(function () {
    const pad = (value) => value.toString().padStart(2, '0');

    const formatTime = (totalSeconds) => {
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = Math.floor(totalSeconds % 60);
        const tenths = Math.floor((totalSeconds % 1) * 10);

        return `${pad(minutes)}:${pad(seconds)}.${tenths}`;
    };

    const parseConfig = (element) => {
        const data = element.getAttribute('data-config');

        if (!data) {
            return {
                mode: 'stopwatch',
                duration: 60,
                intervals: [],
                showNotes: true,
            };
        }

        try {
            return JSON.parse(data);
        } catch (error) {
            console.error('Fitness Timer: Failed to parse configuration', error);
            return {
                mode: 'stopwatch',
                duration: 60,
                intervals: [],
                showNotes: true,
            };
        }
    };

    const createIntervalList = (container, intervals) => {
        container.innerHTML = '';

        if (!intervals || !intervals.length) {
            return;
        }

        const list = document.createElement('ol');
        list.className = 'fitness-timer__interval-list';

        intervals.forEach((interval, index) => {
            const item = document.createElement('li');
            item.className = 'fitness-timer__interval';
            item.dataset.index = index;
            item.innerHTML = `
                <span class="fitness-timer__interval-label">${interval.label}</span>
                <span class="fitness-timer__interval-duration">${interval.duration}s</span>
            `;
            list.appendChild(item);
        });

        container.appendChild(list);
    };

    const updateActiveInterval = (container, activeIndex) => {
        const items = container.querySelectorAll('.fitness-timer__interval');
        items.forEach((item) => {
            item.classList.toggle('fitness-timer__interval--active', Number(item.dataset.index) === activeIndex);
        });
    };

    const Timer = function (element) {
        this.element = element;
        this.config = parseConfig(element);
        this.display = element.querySelector('.fitness-timer__display');
        this.modeDisplay = element.querySelector('.fitness-timer__mode');
        this.startButton = element.querySelector('.fitness-timer__btn--start');
        this.pauseButton = element.querySelector('.fitness-timer__btn--pause');
        this.resetButton = element.querySelector('.fitness-timer__btn--reset');
        this.lapButton = element.querySelector('.fitness-timer__btn--lap');
        this.lapsList = element.querySelector('.fitness-timer__laps');
        this.intervalContainer = element.querySelector('.fitness-timer__intervals');
        this.requestId = null;
        this.baseTime = 0;
        this.elapsed = 0;
        this.isRunning = false;
        this.activeIntervalIndex = 0;
        this.remainingInInterval = this.config.intervals[0]?.duration || this.config.duration;
        this.laps = [];

        createIntervalList(this.intervalContainer, this.config.intervals);
        this.updateModeLabel();
        this.bindEvents();
        this.render();
    };

    Timer.prototype.bindEvents = function () {
        this.startButton.addEventListener('click', () => this.start());
        this.pauseButton.addEventListener('click', () => this.pause());
        this.resetButton.addEventListener('click', () => this.reset());
        this.lapButton.addEventListener('click', () => this.lap());
    };

    Timer.prototype.updateModeLabel = function () {
        const { mode, intervals } = this.config;

        if (mode === 'interval' && intervals.length) {
            this.modeDisplay.textContent = `Interval ${this.activeIntervalIndex + 1} of ${intervals.length}`;
        } else if (mode === 'countdown') {
            this.modeDisplay.textContent = 'Countdown';
        } else {
            this.modeDisplay.textContent = 'Stopwatch';
        }
    };

    Timer.prototype.updateButtons = function () {
        this.startButton.disabled = this.isRunning;
        this.pauseButton.disabled = !this.isRunning;
        this.resetButton.disabled = !this.isRunning && this.elapsed === 0;
        this.lapButton.disabled = !this.isRunning;
    };

    Timer.prototype.render = function () {
        let displayTime;

        if (this.config.mode === 'countdown') {
            const remaining = Math.max(0, this.config.duration - this.elapsed);
            displayTime = formatTime(remaining);

            if (remaining <= 0) {
                this.pause();
            }
        } else if (this.config.mode === 'interval' && this.config.intervals.length) {
            displayTime = formatTime(Math.max(0, this.remainingInInterval));
        } else {
            displayTime = formatTime(this.elapsed);
        }

        this.display.textContent = displayTime;
        this.updateButtons();
    };

    Timer.prototype.tick = function (timestamp) {
        if (!this.baseTime) {
            this.baseTime = timestamp - this.elapsed * 1000;
        }

        this.elapsed = (timestamp - this.baseTime) / 1000;

        if (this.config.mode === 'interval' && this.config.intervals.length) {
            this.updateIntervalProgress();
        }

        this.render();
        this.requestId = requestAnimationFrame(this.tick.bind(this));
    };

    Timer.prototype.updateIntervalProgress = function () {
        const intervals = this.config.intervals;
        let elapsed = this.elapsed;

        for (let index = 0; index < intervals.length; index += 1) {
            const interval = intervals[index];
            if (elapsed < interval.duration) {
                if (this.activeIntervalIndex !== index) {
                    this.activeIntervalIndex = index;
                    updateActiveInterval(this.intervalContainer, index);
                    this.updateModeLabel();
                }

                this.remainingInInterval = interval.duration - elapsed;
                return;
            }

            elapsed -= interval.duration;
        }

        this.pause();
        this.remainingInInterval = 0;
        updateActiveInterval(this.intervalContainer, intervals.length - 1);
    };

    Timer.prototype.start = function () {
        if (this.isRunning) {
            return;
        }

        this.isRunning = true;
        this.baseTime = performance.now() - this.elapsed * 1000;
        this.requestId = requestAnimationFrame(this.tick.bind(this));
        this.updateButtons();
    };

    Timer.prototype.pause = function () {
        if (!this.isRunning) {
            return;
        }

        this.isRunning = false;

        if (this.requestId) {
            cancelAnimationFrame(this.requestId);
            this.requestId = null;
        }

        this.updateButtons();
    };

    Timer.prototype.reset = function () {
        this.pause();
        this.elapsed = 0;
        this.laps = [];
        this.baseTime = 0;
        this.activeIntervalIndex = 0;
        this.remainingInInterval = this.config.intervals[0]?.duration || this.config.duration;
        this.lapsList.innerHTML = '';
        updateActiveInterval(this.intervalContainer, null);
        this.updateModeLabel();
        this.render();
    };

    Timer.prototype.lap = function () {
        if (!this.isRunning) {
            return;
        }

        const lapTime = this.display.textContent;
        this.laps.push(lapTime);

        const listItem = document.createElement('li');
        listItem.textContent = `Lap ${this.laps.length}: ${lapTime}`;
        this.lapsList.prepend(listItem);
    };

    const init = () => {
        const timers = document.querySelectorAll('.fitness-timer');

        timers.forEach((timerElement) => {
            if (!timerElement.dataset.instance) {
                timerElement.dataset.instance = 'initialized';
                new Timer(timerElement); // eslint-disable-line no-new
            }
        });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
