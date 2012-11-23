(($) ->

    # View to display after logging in.
    defaultView = "main"

    showMessage = ($messageEl, message) ->
        $messageEl.html message 

    apiErrorHandler = ($errorEl, xhr) ->
        errorMessage = ""
        try
            errorResult = $.parseJSON xhr.responseText
            errorMessage = errorResult.error
        catch e
            errorMessage = xhr.responseText
            if !errorMessage
                errorMessage = "Error: " + xhr.status

        showMessage $errorEl, errorMessage

    SECOND = 1000
    MINUTE = SECOND * 60
    HOUR = MINUTE * 60
    DAY = HOUR * 24

    formatTime = (time, now) ->
        if typeof time is "number"
            time = new Date time
        if now
            if typeof now is "number"
                now = new Date now
        else
            now = new Date

        answer = ""

        delta = now.getTime() - time.getTime()
        if delta < 0
            answer = "now"
        else if delta < MINUTE
            answer = "#{(delta / SECOND).toFixed 0}s ago"
        else if delta < HOUR
            answer = "#{(delta / MINUTE).toFixed 0}m ago"
        else if delta < DAY
            answer = "#{time.getHours()}:#{time.getMinutes()}"
        else if delta < (DAY * 31)
            answer = "This month"
        else
            answer = "Long ago"

        return answer

    #### A contact
    # Has the following fields:
    #  - `name` the nickname for this contact.
    #  - `phoneNumber` the phone number for this contact.
    #  - `subscribed` true if the user is subscribed to this contact, false otherwise.
    #  - `isDefaultSender` true if this user is the default sender, and can't be deleted.
    window.Contact = Backbone.Model.extend({
        defaults: () ->
            name: ''
            phoneNumber: ''
            subscribed: false
            isDefaultSender: false
    })

    #### A list of Contacts
    window.Contacts = Backbone.Collection.extend
        model: Contact,
        url: '/api/admin/contacts'


    #### A log entry
    # Has the following fields:
    #  - `time` milliseconds since the epoch, UTC.
    #  - `direction` "to" the owner, or "from" the owner.
    #  - `contact` the name of the contact, or the number the message was sent
    #    from/to.
    #  - `message` the log message.
    window.LogEntry = Backbone.Model.extend({
    })

    #### A list of LogEntry objects
    window.LogEntries = Backbone.Collection.extend
        model: LogEntry,
        url: '/api/admin/log'

        parse: (response) ->
            @serverTime = new Date(response.now)
            return response.logItems

    window.LoginView = Backbone.View.extend
        events:
            'click .loginButton'    : 'login'
            'keypress input'        : 'loginOnEnter'

        initialize: () ->
            _.bindAll this, "render"
            @template = _.template($('#login-template').html())

        render: () ->
            renderedContent = @template
            $(@el).html(renderedContent)
            return this

        loginOnEnter: (event) ->
            if (event.keyCode == 13)
                @login(event)

        login: (event) ->
            # TODO: Do we need to escape the password here or encode it or something?
            event.preventDefault()
            self = this
            $.ajax
                type: 'POST'
                url: '/api/login'
                data: 'password=' + @$('.password').val()
                success: () ->
                    window.app.navigate defaultView, true

                error: (xhr, textStatus, errorThrown) ->
                    apiErrorHandler self.$('.errorText'), xhr

    window.ContactView = Backbone.View.extend
        tagName: 'li'
        className: 'listItem selectable'

        initialize: () ->
            _.bindAll this, "render"
            @template = _.template($('#contact-template').html())
            @model.on 'change', @render

        render: () ->
            renderedContent = @template @model.toJSON()
            $(@el).html(renderedContent)
            return this

    #### A contact in the ContactEditorView
    # These views keep track of whether or not they've been selected.  The
    # ContactEditorView keeps track of all ContactEditorContactViews, so it
    # can work out which are selected.
    window.ContactEditorContactView = window.ContactView.extend
        events:
            'click': 'clicked'

        selected: false

        clicked: () ->
            @selected = !@selected
            @trigger 'selectionChanged', @selected
            if @selected
                $(@el).addClass('selected')
            else
                $(@el).removeClass('selected')


    #### Editable list of contacts
    window.ContactEditorView = Backbone.View.extend
        events:
            'click .addButton'    : 'addNewContact'
            'keypress input'      : 'addNewContactOnEnter'
            'click .deleteButton' : 'deleteContacts'
            'click .inviteButton' : 'inviteContacts'

        initialize: () ->
            _.bindAll this, "render"
            @template = _.template($('#contact-list-template').html())
            @collection.on 'all', @render
            @contactViews = []

        render: () ->
            self = this
            $(@el).html this.template()
            $contacts = @$('.contacts')

            contactViews = @contactViews = []

            @collection.each (contact) ->
                # TODO: Need to destroy old ContactEditorContactView objects if there are any
                view = new ContactEditorContactView
                    model: contact
                    collection: @collection
                view.on 'selectionChanged', (selected) ->
                    self.childSelected selected
                contactViews.push view
                $contacts.append view.render().el

            return this

        childSelected: (selected) ->
            $enabledWhenSelectionButtons = @$('.enabledWhenUsersSelected')

            console.log this
            selectedRows = @getSelectedRows()
            if selectedRows.length > 0
                $enabledWhenSelectionButtons.removeAttr('disabled')
            else
                $enabledWhenSelectionButtons.attr('disabled', true)

            # TODO: Activate/deactivate delete button

        # Returns a {index, model} for each selected row in this ContactEditorView.
        getSelectedRows: () ->
            answer = []
            for contactView, index in @contactViews
                if contactView.selected
                    answer.push
                        index: index
                        model: contactView.model

            return answer


        addNewContactOnEnter: (event) ->
            if (event.keyCode == 13)
                @addNewContact(event)

        addNewContact: (event) ->
            event.preventDefault()

            @$('.addButton').attr("disabled", true)

            @$('.errorText').html ""

            newContact = 
                name: @$(".nameInput").val()
                phoneNumber: @$(".numberInput").val()

            onError = (model, xhr, options) ->
                errorResult = $.parseJSON xhr.responseText
                @$('.errorText').html errorResult.error
                @$('.addButton').attr("disabled", false)


            @collection.create newContact, {wait: true, error: onError}

            return false

        deleteContacts: () ->
            selectedRows = @getSelectedRows()
            for row in selectedRows
                model = row.model           
                if not model.get 'isDefaultSender'
                    model.destroy()

            return false

        inviteContacts: () ->
            self = this
            selectedIds = _.map @getSelectedRows(), (row) ->
                row.model.id
            $.ajax
                type: 'POST'
                url: '/api/invite'
                data: JSON.stringify(selectedIds)
                success: (data, textStatus, xhr) ->
                    showMessage self.$('.errorText'), "#{data.length} invite#{if data.length != 1 then "s" else ""} sent."

                error: (xhr, textStatus, errorThrown) ->
                    apiErrorHandler self.$('.errorText'), xhr

            return false


    #### List of log entries
    window.LogView = Backbone.View.extend
        #events:
            # TODO: Add refresh button
            #'click .refreshButton': 'refresh'

        initialize: () ->
            _.bindAll this, "render"
            @template = _.template($('#log-list-template').html())
            @logEntryTemplate = _.template($('#log-entry-template').html())
            @collection.on 'all', @render

        render: () ->
            self = this
            $(@el).html @template()

            @renderLogEntries()

            return this

        renderLogEntries: () ->
            self = this
            $logEntries = @$('.logEntries')
            $logEntries.empty()

            now = @collection.now
            @collection.each (log) ->
                jsonLogEntry = log.toJSON()
                jsonLogEntry.timeStr = formatTime jsonLogEntry.time, now
                $logEntries.append self.logEntryTemplate jsonLogEntry

            return this
    
    #### List of log entries
    window.SmsWidgetView = Backbone.View.extend
        events:
            'click .sendMessageButton': 'sendSms'

        initialize: () ->
            _.bindAll this, "render"
            @template = _.template($('#sms-widget').html())

        render: () ->
            self = this
            $(@el).html @template()
            return this

        sendSms: (event) ->
            event.preventDefault()
            self = this
            data =
                to: @$('.numberInput').val()
                message:  @$('.messageInput').val()
            $.ajax
                type: 'POST'
                url: '/api/sendSms'
                data: JSON.stringify(data)
                success: () ->
                    # Refresh the log entries:
                    window.logEntries.fetch()
                    self.$(':text').val("")

                error: (xhr, textStatus, errorThrown) ->
                    apiErrorHandler self.$('.errorText'), xhr
            return false

    window.contacts = new window.Contacts()
    window.logEntries = new window.LogEntries()

    #### Router
    window.XmppVoiceMail = Backbone.Router.extend
        routes:
            ''     : 'login'
            'main' : 'main'

        initialize: () ->
            @loginView = new LoginView()
            @$main = $('#main')

            @contactEditorView = new ContactEditorView
                collection: window.contacts

            @logView = new LogView
                collection: window.logEntries

            @smsWidgetView = new SmsWidgetView()

        login: () ->
            @$main.empty()
            @$main.append @loginView.render().el

        main: () ->
            window.contacts.fetch()
            window.logEntries.fetch()
            @$main.empty()
            @$main.append @contactEditorView.render().el
            @$main.append @logView.render().el
            @$main.append @smsWidgetView.render().el

)(jQuery)