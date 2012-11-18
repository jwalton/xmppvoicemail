(($) ->
    #### A contact
    # Has the following fields:
    #  - `name` the nickname for this contact.
    #  - `phoneNumber` the phone number for this contact.
    #  - `subscribed` true if the user is subscribed to this contact, false otherwise.
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

    window.ContactView = Backbone.View.extend
        tagName: 'li'
        className: 'listItem'

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
            'click .deleteButton' : 'deleteContacts'

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
            deleteButton = @$('deleteButton')

            console.log this
            selectedRows = @getSelectedRows()
            if selectedRows.length > 0
                @$('.deleteButton').removeAttr('disabled')
            else
                @$('.deleteButton').attr('disabled', true)

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

        addNewContact: () ->
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

        deleteContacts: () ->
            selectedRows = @getSelectedRows()
            for row in selectedRows
                model = row.model           
                if not model.get 'isDefaultSender'
                    model.destroy()

    
    window.contacts = new window.Contacts()

    #### Router
    window.XmppVoiceMail = Backbone.Router.extend
        routes:
            '': 'contactEditor'

        initialize: () ->
            @contactEditorView = new ContactEditorView
                collection: window.contacts
            contacts.fetch()

        contactEditor: () ->
            $main = $('#main')
            $main.empty()
            $main.append @contactEditorView.render().el

)(jQuery)